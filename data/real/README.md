# Put your real event log here

UnJam only analyses real logs. Recommended: **BPI Challenge 2012** (a loan / overdraft application
process of a Dutch financial institution, about 13,000 applications).

1. Open https://data.4tu.nl/articles/dataset/BPI_Challenge_2012/12689204/1
2. Read the licence ("4TU General Terms of Use") and the citation request on that page.
3. Download `BPI_Challenge_2012.xes.gz` (about 3.3 MB). Do NOT unzip it; UnJam reads `.gz` directly.
4. Save it in this folder: `data/real/BPI_Challenge_2012.xes.gz`

Citation: van Dongen, B.F. (2012). BPI Challenge 2012. 4TU.ResearchData.
https://doi.org/10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f

The file is ignored by git on purpose, so you do not re-publish someone else's data.
Other logs also work: any `.xes`, `.xes.gz`, `.csv` or `.zip` with a case id, an activity and a timestamp.
