# Step1 Fast Track (repo: Step1-Fast-Track)

USMLE Step 1 prep web app. Static site served by GitHub Pages, installed on phones from Safari (Add to Home Screen).
Separate product from Learn Echo (Learnecho/SPI-Practice); its engine was copied here as a starting point. Never change Learn Echo from this repo.

## Every change: bump the version
1. Increase `v` in `version.json` by 1.
2. Set `var APPV=` in index.html to the same number.
3. Set `?v=` on the script tags in index.html (question files and labs.js) to the same number.

## Question bank (goal: 3,000)
- Row: [system, stem, options (5), answerIndex, explanation, 1 = "New, unchecked" until the owner (a physician) reviews it, "F"/"C" level, discipline].
- Question files are APPEND-ONLY: progress is stored by question index. Never reorder, delete or insert. Fix a question in place. New files go at the END of the q/ script list in index.html.
- Write batches in tools/qsrc/<name>.py, then `python3 tools/build_questions.py <module> <q-file-name>` (shuffles answer positions with a fixed seed).
- Systems and weights follow the USMLE Step 1 content specifications (usmle.org), midpoint of each range: Human development 2, Blood & immune 11, Nervous system & behavior 12, Musculoskeletal & skin 10, Cardiovascular 9, Respiratory & renal 13, Gastrointestinal 8, Reproductive & endocrine 14, Multisystem 10, Biostatistics & epidemiology 5, Communication & ethics 7.5. Keep system names exactly as in BP in index.html. Fill the biggest gaps first (Progress tab shows coverage).
- Disciplines: Pathology, Physiology, Pharmacology, Microbiology, Immunology, Biochemistry, Genetics, Anatomy, Embryology, Behavioral science, Histology & cell biology, Nutrition.
- Original questions only. Never copy from UWorld, Amboss, NBME, First Aid or any other paid source.
- Stems must be exam-style clinical vignettes (about 90 to 150 words): age and sex, presenting problem, history, medications, social and family history, vital signs, exam, labs (one per line), with some irrelevant details. Do not name the diagnosis; make the student work it out, then answer a second-step question (mechanism, next step, drug, complication). End with "Which of the following...?".
- Batches done: s1_batch1 (100, all systems; vignette stems in tools/qsrc/s1_batch1_long.py).

## Features
- Today's goal from the study plan (exam date + hours/day), mixing due reviews (~60%) with new questions.
- Spaced repetition (gaps 1, 2, 4, 7, 14, 30 days).
- Timed exam blocks like the real exam: 20 questions per 30 minutes, weighted by system.
- Study plan: days left, daily goal, focus systems (weight x weakness), phases (Build, Sharpen, Final week).
- Lab values: labs.js (LABS: category, test, range, teaching note, high-yield flag). Labs tab (tutorial with search, categories, ★ high-yield filter) and a "Lab values" button on every question that opens the same table over the question, like the real exam. Original notes only.
- Planned: explanations in Pashto, Dari and Urdu (language toggle); images.
