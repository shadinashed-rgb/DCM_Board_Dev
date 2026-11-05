#!/usr/bin/env python3
"""Prepare schema-aware manual Starburst sample queries for SIG07 application ratings.

Only local cohort evidence is read. No database connection, namespace approval,
advisory trigger, or source-field assumption is made by generation.
"""
import argparse
from collections import defaultdict
from datetime import date, timedelta
import csv
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parent
TABLE='"delta"."prod_credit_and_lending_gda"."application_ratings"'
GROUPS={'MG001356':'VODAFONE','MG102229':'Siemens Energy','MG101624':'SOFTBANK'}
ROUTES={
    'MASTERGROUP_ID':['mastergroup_id','master_group_id','drr_mastergroup_id','rct_mastergroup_id','mastergroup_esr_identifier'],
    'CIN':['cin','obligor_cin','customer_cin','customer_relationship_cin_identifier'],
    'GID':['gid','rct_gid','customer_gid','customer_relationship_gid_identifier'],
    'RELATIONSHIP_ID':['relationship_id','app_relationship_id'],
    'APPLICATION_SERIAL_NUMBER':['application_serial_number','application_serial_no'],
    'CREDIT_PROPOSAL_SERIAL_NO':['credit_proposal_serial_no','credit_proposal_serial_number'],
}


def literal(value):
    return "'"+str(value).replace("'","''")+"'"


def identifiers(cohort_dir):
    """Retain original identifier roles and source/date provenance for discovery."""
    db=sqlite3.connect((Path(cohort_dir).resolve()/'cohort.sqlite').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    result=defaultdict(set)
    for group in GROUPS:
        result[(group,'MASTERGROUP_ID',group)].add('user_supplied_mastergroup')
    native={'clo':('rct_mastergroup_id',{'CIN':'obligor_cin','GID':'rct_gid'}),
            'drr':('drr_mastergroup_id',{'CIN':'cin','GID':'gid'}),
            'counterparty':('mastergroup_esr_identifier',{'CIN':'customer_relationship_cin_identifier','GID':'customer_relationship_gid_identifier'})}
    for row in db.execute('SELECT * FROM raw_rows'):
        p=json.loads(row['payload']);source=row['source']
        if source in native:
            group_col,fields=native[source];group=p.get(group_col)
            if group not in GROUPS:continue
            for kind,col in fields.items():
                value=str(p.get(col) or '').strip().upper()
                if value and value not in ('XNA','NO MSG','N/A','0','NULL','NONE'):
                    result[(group,kind,value)].add(f'{source}.{col} observed {row["observation_date"]}')
    # Facilities routes are candidate application bridges, not native application keys.
    for row in db.execute("SELECT r.*,m.mastergroup_id FROM raw_rows r JOIN matches m USING(source,raw_id) WHERE r.source='facilities' AND m.status='matched'"):
        p=json.loads(row['payload']);group=row['mastergroup_id']
        if group not in GROUPS:continue
        for kind,col in [('CIN','cin'),('RELATIONSHIP_ID','relationship_id'),('APPLICATION_SERIAL_NUMBER','application_serial_number'),('CREDIT_PROPOSAL_SERIAL_NO','credit_proposal_serial_no')]:
            value=str(p.get(col) or '').strip().upper()
            if value and value not in ('XNA','N/A','0','NULL','NONE'):
                result[(group,kind,value)].add(f'facilities.{col} observed {row["observation_date"]}; development cohort mapping')
    db.close()
    return [dict(mastergroup_id=g,client_name=GROUPS[g],identifier_kind=k,identifier_value=v,evidence=' | '.join(sorted(provenance))) for (g,k,v),provenance in sorted(result.items())]


def metadata_query(seeds,as_of='2026-11-04',lookback_days=120,per_type=25):
    end=date.fromisoformat(as_of)
    if lookback_days<1 or per_type<1:raise ValueError('Positive lookback/per-type sample sizes required')
    start=(end-timedelta(days=lookback_days)).strftime('%Y%m%d');upper=end.strftime('%Y%m%d')
    clients=',\n    '.join('('+literal(g)+', '+literal(n)+')' for g,n in GROUPS.items())
    unique=sorted({(r['mastergroup_id'],r['identifier_kind'],r['identifier_value']) for r in seeds})
    inventory=',\n    '.join('('+', '.join(map(literal,r))+')' for r in unique)
    routes=',\n    '.join('('+literal(k)+', '+literal(c)+')' for k,cols in ROUTES.items() for c in cols)
    # CONCAT/CHR avoid nested literal quoting while assembling the returned SQL text.
    return f'''-- READ ONLY METADATA QUERY. This does NOT execute application_ratings data SQL.
-- Returns one sample_sql/profile_sql pair per client using columns visible NOW.
-- Identifier matches and column-role synonyms are discovery candidates only.
-- Do not interpret a credit-rating record as advisory activity automatically.
WITH clients(mastergroup_id, client_name) AS (
  VALUES {clients}
), seed_ids(mastergroup_id, identifier_kind, identifier_value) AS (
  VALUES {inventory}
), routes(identifier_kind, candidate_column) AS (
  VALUES {routes}
), available AS (
  SELECT column_name, data_type, ordinal_position
  FROM "delta".information_schema.columns
  WHERE table_schema='prod_credit_and_lending_gda' AND table_name='application_ratings'
), scalar_columns AS (
  SELECT * FROM available WHERE
    LOWER(data_type) LIKE 'varchar%' OR LOWER(data_type) LIKE 'char%'
    OR LOWER(data_type) IN ('integer','bigint','smallint','tinyint','double','real','date')
    OR LOWER(data_type) LIKE 'decimal%' OR LOWER(data_type) LIKE 'timestamp%'
), matched AS (
  SELECT DISTINCT s.mastergroup_id, s.identifier_kind, s.identifier_value, a.column_name
  FROM seed_ids s JOIN routes r ON r.identifier_kind=s.identifier_kind
  JOIN scalar_columns a ON LOWER(a.column_name)=r.candidate_column
), eligible_routes AS (
  -- Prefer explicit group/CIN/GID lookups. Broad application/relationship serial
  -- discovery is only used when that client has no primary identifier route.
  SELECT m.* FROM matched m
  WHERE m.identifier_kind IN ('MASTERGROUP_ID','CIN','GID') OR NOT EXISTS (
    SELECT 1 FROM matched primary_match WHERE primary_match.mastergroup_id=m.mastergroup_id
      AND primary_match.identifier_kind IN ('MASTERGROUP_ID','CIN','GID')
  )
), predicates AS (
  SELECT mastergroup_id, identifier_kind, column_name,
    CONCAT('UPPER(TRIM(CAST(t.',CHR(34),REPLACE(column_name,CHR(34),CONCAT(CHR(34),CHR(34))),CHR(34),
      ' AS VARCHAR))) IN (',
      ARRAY_JOIN(ARRAY_AGG(CONCAT(CHR(39),REPLACE(identifier_value,CHR(39),CONCAT(CHR(39),CHR(39))),CHR(39))),', '),')') AS predicate
  FROM eligible_routes GROUP BY mastergroup_id, identifier_kind, column_name
), client_routes AS (
  SELECT mastergroup_id, ARRAY_JOIN(ARRAY_AGG(predicate),' OR ') AS client_predicate,
    ARRAY_JOIN(ARRAY_AGG(CONCAT(identifier_kind,':',column_name)),', ') AS matched_columns
  FROM predicates GROUP BY mastergroup_id
), ranked_dates AS (
  SELECT column_name, ROW_NUMBER() OVER (ORDER BY
    CASE LOWER(column_name) WHEN 'run_date' THEN 1 WHEN 'reporting_date' THEN 2
      WHEN 'as_of_date' THEN 3 WHEN 'snapshot_date' THEN 4 ELSE 5 END) AS rn
  FROM scalar_columns
  WHERE LOWER(column_name) IN ('run_date','reporting_date','as_of_date','snapshot_date','data_as_of_date')
), date_choice AS (
  SELECT column_name,
    CONCAT('SUBSTR(REPLACE(TRIM(CAST(t.',CHR(34),REPLACE(column_name,CHR(34),CONCAT(CHR(34),CHR(34))),CHR(34),
      ' AS VARCHAR)),',CHR(39),'-',CHR(39),',',CHR(39),CHR(39),'),1,8)') AS date_expression
  FROM ranked_dates WHERE rn=1
), dimension_candidates AS (
  SELECT column_name,
    CASE WHEN LOWER(column_name) IN ('rating_type','rating_type_code','application_rating_type','application_rating_type_code') THEN 'type' ELSE 'provider' END AS family,
    ordinal_position
  FROM scalar_columns WHERE LOWER(column_name) IN
    ('rating_type','rating_type_code','application_rating_type','application_rating_type_code',
     'rating_agency','rating_agency_code','rating_provider','agency','agency_name')
), ranked_dimensions AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY family ORDER BY ordinal_position) AS rn FROM dimension_candidates
), dimensions AS (
  SELECT ARRAY_JOIN(ARRAY_AGG(CONCAT('t.',CHR(34),REPLACE(column_name,CHR(34),CONCAT(CHR(34),CHR(34))),CHR(34))),', ') AS refs,
    ARRAY_JOIN(ARRAY_AGG(column_name),', ') AS dimension_columns
  FROM ranked_dimensions WHERE rn=1
), rating_fields AS (
  SELECT ARRAY_JOIN(ARRAY_AGG(column_name),', ') AS rating_related_columns FROM available
  WHERE REGEXP_LIKE(LOWER(column_name),'rating|crr|agency|grade|standard|poor|mood|fitch')
), context AS (
  SELECT c.*, p.client_predicate, p.matched_columns, d.column_name AS snapshot_column,
    d.date_expression, COALESCE(m.refs,'') AS dimension_refs,
    COALESCE(m.dimension_columns,'') AS sample_dimensions, f.rating_related_columns,
    CONCAT(d.date_expression,' BETWEEN ',CHR(39),'{start}',CHR(39),' AND ',CHR(39),'{upper}',CHR(39)) AS date_predicate
  FROM clients c LEFT JOIN client_routes p ON p.mastergroup_id=c.mastergroup_id
  LEFT JOIN date_choice d ON TRUE CROSS JOIN dimensions m CROSS JOIN rating_fields f
)
SELECT mastergroup_id, client_name, matched_columns, snapshot_column,
       sample_dimensions, rating_related_columns,
       CASE WHEN NOT EXISTS (SELECT 1 FROM available) THEN 'schema_not_visible'
         WHEN client_predicate IS NULL THEN 'identifier_bridge_required'
         WHEN date_expression IS NULL THEN 'snapshot_date_column_required'
         ELSE 'candidate_sample_sql_ready' END AS plan_status,
       CASE WHEN client_predicate IS NOT NULL AND date_expression IS NOT NULL THEN
         CONCAT('-- Client ',client_name,' ',mastergroup_id,CHR(10),
           '-- Discovery sample. Verify date format (YYYYMMDD or ISO) and partition bounds.',CHR(10),
           '-- Identical application IDs may have different rating types, providers or dates.',CHR(10),
           'WITH sampled AS (SELECT t.*, ',date_expression,' AS _sig07_observation_date, ',
           'ROW_NUMBER() OVER (',CASE WHEN dimension_refs='' THEN '' ELSE CONCAT('PARTITION BY ',dimension_refs,' ') END,
           'ORDER BY ',date_expression,' DESC) AS _sig07_sample_rank FROM {TABLE} t WHERE ',
           date_predicate,' AND (',client_predicate,')) SELECT * FROM sampled WHERE _sig07_sample_rank <= ',
           CASE WHEN dimension_refs='' THEN '100' ELSE '{per_type}' END,
           ' ORDER BY _sig07_observation_date DESC;') END AS sample_sql,
       CASE WHEN client_predicate IS NOT NULL AND date_expression IS NOT NULL THEN
         CONCAT('-- Full type/date counts within the selected client lookup/window; no sample row cap.',CHR(10),
           'SELECT ',date_expression,' AS observation_date',
           CASE WHEN dimension_refs='' THEN '' ELSE CONCAT(', ',dimension_refs) END,
           ', COUNT(*) AS raw_rows FROM {TABLE} t WHERE ',date_predicate,
           ' AND (',client_predicate,') GROUP BY ',date_expression,
           CASE WHEN dimension_refs='' THEN '' ELSE CONCAT(', ',dimension_refs) END,
           ' ORDER BY observation_date DESC;') END AS profile_sql
FROM context ORDER BY mastergroup_id;
'''


def build(cohort_dir,output,as_of='2026-11-04'):
    output=Path(output)
    if output.exists():raise ValueError('Output exists; choose a new folder')
    seeds=identifiers(cohort_dir)
    output.mkdir(parents=True)
    (output/'01_columns.sql').write_text(f'SHOW COLUMNS FROM {TABLE};\n')
    (output/'02_table_definition.sql').write_text(f'SHOW CREATE TABLE {TABLE};\n')
    (output/'03_generate_client_queries.sql').write_text(metadata_query(seeds,as_of))
    (output/'04_rating_column_inventory.sql').write_text('''-- READ ONLY METADATA; candidate names are clues, not confirmed definitions.
SELECT column_name, data_type, ordinal_position
FROM "delta".information_schema.columns
WHERE table_schema='prod_credit_and_lending_gda' AND table_name='application_ratings'
  AND REGEXP_LIKE(LOWER(column_name),'rating|crr|agency|grade|standard|poor|mood|fitch|application|approval|effective|status|date')
ORDER BY ordinal_position;
''')
    with (output/'client_identifier_candidates.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(seeds[0]));w.writeheader();w.writerows(seeds)
    (output/'generation_manifest.json').write_text(json.dumps(dict(source_table=TABLE,signal='SIG07',as_of=as_of,source_cohort=str(Path(cohort_dir).resolve()),identifier_candidates=len(seeds),stage='metadata_and_samples_pending',scope='Three client discovery; no source namespace, current-rating selection or advisory trigger approved'),indent=2)+'\n')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',required=True);parser.add_argument('--out',required=True)
    parser.add_argument('--as-of',default='2026-11-04')
    args=parser.parse_args();print(build(args.cohort,args.out,args.as_of))
