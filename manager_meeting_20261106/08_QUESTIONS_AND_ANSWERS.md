# Likely questions and suggested answers

**Q1. So does it work?**
Yes, end to end on real data for three clients. The engine extracts, links, tests and explains every record, and the board presents it. What is limited is the *data*: one signal (SIG02) produces candidates today. SIG01 is one data field away from working.

**Q2. Why only one live signal after all this work?**
Most of the work was making the data trustworthy: identity matching across CIN, GID and PVD, de-duplication, snapshot selection, lineage, and honest handling of missing data. That foundation is reusable. The missing pieces are sources nobody has supplied yet:
- the LoanIQ drawn amount
- derivatives trades
- covenant tests
- CME call reports

**Q3. Is anything here actionable for a banker today?**
Potentially the SoftBank case. A new USD 400m facility was approved by credit on 17 Sep 2026. The same facility ID shows USD 179.7m drawn as a Cat A term loan, and DRR shows the same USD 179.7m of USD 400m utilised. Separately, Vodafone has 7 facilities approved on 17 Sep. Both need validation with the credit team before anyone acts on them.

**Q4. How do we know these signals actually predict bond issuance?**
We don't yet. That is why the recommendation includes a back-test against the completed-deals file and Dealogic: did the signals appear 3–12 months before past issuances? It is cheap and it gives the business case.

**Q5. How long would a real version take?**
The board itself takes days to weeks; it already exists. The timeline is driven by data access and entity mapping. Indicatively, a 20–30 client pilot takes 6–8 weeks *after* LoanIQ and credit data access is granted. A production rollout is a further quarter. CME call reports depend on a governance review that could take months.

**Q6. What do you need from me?**
- Sponsorship of the data requests (credit, LoanIQ, markets).
- A decision on the pilot scope.
- Starting the CME governance conversation.
- Time and a data engineer for 6–8 weeks.
- Agreement on where the board will live (AI Markets).

**Q7. Can this be automated daily, as Jerome wants?**
Not with manual Starburst extracts. It needs scheduled extracts or AI Markets ingestion, owned by a data team. Phase 1 can be weekly; daily is a Phase 2 goal.

**Q8. Is there any compliance / MNPI risk?**
The board shows internal credit data to DCM bankers, who are private side; that needs confirmation of permitted use and entitlements. CME call reports carry explicit MNPI concerns; they are excluded until governance agrees a route.

**Q9. Why not just add an AI model to predict issuers?**
Without proven signals and history, a model would be guessing. The back-test in Phase 1 produces exactly the labelled history a model needs. If it shows signal, Phase 3 can explore a score (Simonti's approach), with model governance.

**Q10. How does this relate to the LAF board?**
Same design, same entity-matching problem, same news feed. The sensible target is one platform with an LAF view and a DCM view, sharing the client mapping and the data feeds.

**Q11. What if the data owners can't provide the data?**
Then the board remains a two-signal tool (new facilities plus maturity windows, plus news). That may still be useful to DCM, but less differentiated. Knowing this early is valuable in itself; the pilot forces the answer.

**Q12. What are the main risks?**

| Risk | Mitigation |
|---|---|
| Data not accessible | Sponsorship |
| Signals don't predict issuance | Back-test |
| Mapping effort | Limit the scope; share the work with LAF |
| CME delays | Decouple CME from Phase 1 |
| Key-person dependency | Data engineer and documented runbook |
| Adoption | Co-design with Jerome |

**Q13. What has changed since the last meetings with DCM?**
All six decisions from those meetings are implemented, and every change is documented:
- the broader Cat A drawing definition with the EUR 50m threshold
- the approval date for bridges
- the two pre-hedging signals
- covenant pressure within half a turn
- call reports for rating advisory
- investor sales dropped

**Q14. How confident are you in the numbers?**
They are reconciled. All 626 earlier records map forward and the 5 new ones are explained. The workbook counts are formulas, and 87 automated tests pass. The caveat: these are development links between sources that still need owner confirmation, as listed in the 44 owner questions.
