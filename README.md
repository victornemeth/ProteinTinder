# Annotate App

A mobile-friendly and web-based app for visualizing 3D protein structures using [3Dmol.js](https://3dmol.csb.pitt.edu/).  
Users can annotate protein models with intuitive swipe gestures:

- 👉 Swipe **right** — mark as **Correct**
- 👈 Swipe **left** — mark as **Wrong**
- 👇 Swipe **down** — mark as **Unsure**

Annotations are saved to a MySQL database with the following fields:

- `protein_id`
- `user_id`
- `user_name`
- `given_annotation` (one of: `correct`, `wrong`, `unsure`)
- `timestamp`

And can be exported to csv from within the webapp.

## Stuff I need to Add

- If you have suggestions please let me know!
- Deploying the website with Debug=False, nginx config.

## Use

- Make a account
- Upload your folder of pdbs as a zip file and add a annotation title (e.g. Correctly Folded?) and description
- The name of the pdb file is also its protein_id

### Protein Architecture

- Check the box **"Include architecture data (CSV files)?"** during upload.
- The uploaded `.zip` file must include both `.pdb` and `.csv` files.
- Each `.csv` file should share the same name as its corresponding `.pdb` file (i.e., `protein_id.csv` and `protein_id.pdb`).

#### Example `.csv` format:

```csv
Domain Number,Start Residue,End Residue,Predicted Domain
1,1,181,XD2
2,182,294,XD3
```

## Features

- 🧬 Interactive 3D protein viewer
- 📱 Touch and mouse swipe support
- 🧮 Overview page to see proteins grouped by annotation.
- 🔐 User authentication (login/signup)
- 💾 Annotations can be exported as csv.

## Tech Stack

- Python / Django
- MySQL
- HTML / JS / 3Dmol.js
- Docker

## Run Locally

```bash
git clone https://github.com/victornemeth/ProteinTinder.git
cd ProteinTinder
docker compose up -d --build
```

Connect via localhost:8000

