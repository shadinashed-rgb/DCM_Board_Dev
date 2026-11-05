"""Identify manually downloaded Starburst files by contents; preserve raw exports."""
from collections import Counter
import csv
import hashlib
import json
import logging
from pathlib import Path
import shutil
import tempfile
import re

SIGNATURES={
 'pvd':{'joi_date','joi_relationship_id','joi_key'},
 'clo':{'run_date','obligor_cin','rct_mastergroup_id','sub_lim_id'},
 'kyc':{'run_date','cin','related_case_id','review_purpose_code'},
 'drr':{'reporting_date','drr_mastergroup_id','utilisation','approved_limit','facility_id'},
 'facilities':{'run_date','facility_id','facility_creation_date','product_code'},
 'covenants':{'run_date','facility_id','covenant_id','active_testing_id'},
 'counterparty':{'run_date','customer_relationship_cin_identifier','customer_relationship_gid_identifier','mastergroup_esr_identifier'}
}

def hash_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def infer_error_source(name):
    lower=Path(name).stem.lower()
    if 'kyc' in lower:return 'kyc'
    if 'pvd' in lower or 'omnia' in lower or 'omina' in lower:return 'pvd'
    if 'clo' in lower:return 'clo'
    if 'covenant' in lower:return 'covenants'
    if 'counterparty' in lower:return 'counterparty'
    if 'drr' in lower:return 'drr'
    if 'facilit' in lower:return 'facilities'
    return None

def inspect_export(path):
    csv.field_size_limit(64*1024*1024)
    path=Path(path);result={'filename':str(path.resolve()),'sha256':hash_file(path),'bytes':path.stat().st_size,'kind':'unknown','source':None,'rows':0}
    with path.open(encoding='utf-8-sig',newline='') as handle:
        prefix=handle.read(2048);handle.seek(0)
        if re.match(r'\s*[\"\']?(?:fail\s+error|query\s+failed|error\b)',prefix,re.I):
            result.update(kind='error',source=infer_error_source(path.name),error=prefix.strip());return result
        reader=csv.reader(handle);first=next(reader,None)
        if not first:result['kind']='empty_file';return result
        header=[value.strip().lower() for value in first];result['columns']=header
        if len(header)==1 and header[0] in ('create table','create view'):
            cell=next(reader,None);ddl=cell[0] if cell else ''
            result['kind']='schema';result['schema_text']=ddl
            for source,table in {'pvd':'pvd_omnia_drr','clo':'clo_cda_contract_lvl','kyc':'.kyc','drr':'drr_facility_limits','facilities':'facilities_limits','covenants':'.covenants','counterparty':'counterparty_core'}.items():
                if table in ddl.lower():result['source']=source;break
            return result
        if set(header)>={'column','type'} or set(header)>={'column_name','data_type'}:
            result['kind']='schema';result['source']=infer_error_source(path.name);return result
        sources=[name for name,required in SIGNATURES.items() if required<=set(header)]
        if len(sources)!=1:
            if 'raw_rows' in header and ('joi_date' in header or 'source_date' in header):result.update(kind='profile',source='pvd' if 'pvd' in path.name.lower() or 'joi_date' in header else None)
            return result
        source=sources[0];result.update(kind='data',source=source)
        if len(set(header))!=len(header) or any(not c or c.startswith('__') for c in header):raise ValueError(path.name+': invalid/duplicate headers')
        row_hashes=Counter();dates=Counter();group_ids=Counter();observed_columns=Counter()
        date_col='joi_date' if source=='pvd' else 'reporting_date' if source=='drr' else 'run_date'
        group_col={'pvd':'joi_relationship_id','clo':'rct_mastergroup_id','drr':'drr_mastergroup_id','counterparty':'mastergroup_esr_identifier'}.get(source)
        for line,values in enumerate(reader,2):
            if len(values)!=len(header):raise ValueError(f'{path.name}:{line}: malformed CSV row')
            row=dict(zip(header,values));canonical=json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(',',':'))
            row_hashes[hashlib.sha256(canonical.encode()).hexdigest()]+=1;result['rows']+=1
            dates[row.get(date_col,'')]+=1
            if group_col:group_ids[row.get(group_col,'')]+=1
        logical=hashlib.sha256(json.dumps([sorted(header),sorted(row_hashes.items())],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        result.update(rowset_sha256=logical,distinct_rows=len(row_hashes),date_counts=dict(sorted(dates.items())),identifier_counts=dict(sorted(group_ids.items())))
    if hash_file(path)!=result['sha256']:raise ValueError(path.name+' changed during inspection')
    return result

def import_exports(input_dir,output):
    source=Path(input_dir).resolve();output=Path(output).resolve()
    if not source.is_dir():raise ValueError('Download/export folder does not exist')
    if output.exists():raise ValueError('Import output exists; choose a new directory')
    if source==output or source in output.parents:raise ValueError('Import output must be outside the incoming folder')
    records=[inspect_export(p) for p in sorted(source.glob('*.csv'))]
    if not records:raise ValueError('No CSV files found in the incoming folder')
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent))
    try:
        included={};duplicates={};source_headers={};source_chunks=Counter()
        for record in records:
            if record['kind']!='data':continue
            name=record['source'];key=(name,record['rowset_sha256'])
            if key in included:
                record['import_status']='duplicate_export_skipped';record['duplicate_of']=included[key];continue
            included[key]=record['filename']
            if not record['rows'] and any(r['kind']=='data' and r['source']==name and r['rows'] for r in records):
                record['import_status']='empty_export_recorded_not_loaded';continue
            header=record['columns']
            if name in source_headers and set(source_headers[name])!=set(header):raise ValueError(name+': different schemas in incoming exports; select a compatible set first')
            source_headers.setdefault(name,header);source_chunks[name]+=1
            target=temp/name/('part-'+str(source_chunks[name]).zfill(3)+'.csv');target.parent.mkdir(parents=True,exist_ok=True)
            with Path(record['filename']).open(encoding='utf-8-sig',newline='') as incoming,target.open('w',encoding='utf-8',newline='') as outgoing:
                reader=csv.DictReader(incoming);writer=csv.writer(outgoing);writer.writerow(source_headers[name])
                for row in reader:
                    values={k.strip().lower():v for k,v in row.items()};writer.writerow([values[c] for c in source_headers[name]])
            record['import_status']='imported';record['local_csv']=str(target.relative_to(temp))
            metadata={'input_export':record['filename'],'input_sha256':record['sha256'],'query_origin':'Manual Starburst SQL execution and export; submitted SQL not provided','rows':record['rows'],'outcome':'empty' if not record['rows'] else 'data','note':'Partial overlaps across different non-identical exports are preserved, not deduplicated.'}
            target.with_suffix('.metadata.json').write_text(json.dumps(metadata,indent=2))
        template=Path(__file__).resolve().parent/'inputs/approved_identifiers.csv'
        # Always create a header-only review template; never copy local approvals.
        with template.open(encoding='utf-8-sig',newline='') as h:columns=next(csv.reader(h))
        with (temp/'approved_identifiers.csv').open('w',encoding='utf-8',newline='') as h:csv.writer(h).writerow(columns)
        manifest={'incoming_folder':str(source),'files':records,'policy':'Original exports are unchanged. Whole-file duplicates use content-multiset fingerprints, independent of row order. Errors, schemas and profiles are not ingested as data.'}
        (temp/'import_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
        lines=['# Manual Starburst export import','','Copy SQL into Starburst, execute/export to your drive, transfer the export folder, then run this importer locally. No database connection is made.','','| File | Source | Kind | Rows | Import outcome |','| --- | --- | --- | ---: | --- |']
        for record in records:lines.append(f"| {Path(record['filename']).name} | {record['source'] or 'Unidentified'} | {record['kind']} | {record['rows']} | {record.get('import_status','Metadata/error only')} |")
        lines += ['','The error files remain recorded in import_manifest.json; coverage will distinguish extraction_failed from missing_file. Header-only exports do not establish absence of source data. Partial overlaps between different exports require review.','']
        (temp/'IMPORT_REPORT.md').write_text('\n'.join(lines))
        assert all(hash_file(Path(r['filename']))==r['sha256'] for r in records)
        temp.rename(output);logging.info('Manual exports prepared: %s',output);return output
    except Exception:
        logging.exception('Import staging retained at %s',temp);raise
