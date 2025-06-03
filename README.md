# Annotate App

A mobile-friendly and web-based app for visualizing and annotating 3D protein structures using [3Dmol.js](https://3dmol.csb.pitt.edu/) and [NGL.js](https://www.npmjs.com/package/ngl).

## Three use-cases

### Swipe annotations
Users can annotate protein models with intuitive swipe gestures:

- 👉 Swipe **right** — mark as **Correct**
- 👈 Swipe **left** — mark as **Wrong**
- 👇 Swipe **down** — mark as **Unsure**

Annotations are saved to a MySQL database and can be exported to csv from within the webapp.

### Domain annotation
Users can also annotate domains on the uploaded pdb files and export them to csv or fasta (per domain entry):

- Drag across the domain bar to create new domains
- Name the domains using the textbox below the domain
- Expand or crop your domain by dragging at the borders

Annotated domains can be exported from the overview page with the download button:
- CSV per protein, format see Example `.csv` format below
- FASTA per protein, containing all domains as a seperate entry in the fasta file

### Domain correction
Users can also upload their protein structures together with the CSV files that contain their annotated domains:
- Select the wrong domains

How to use:

- Check the box **"Include architecture data (CSV files)?"** during upload.
- The uploaded `.zip` file must include both `.pdb` and `.csv` files.
- Each `.csv` file should share the same name as its corresponding `.pdb` file (i.e., `protein_id.csv` and `protein_id.pdb`).

#### Example `.csv` format:

```csv
Domain Number,Start Residue,End Residue,Predicted Domain
1,1,181,XD2
2,182,294,XD3
```

## Stuff I need to Add

- If you have suggestions please let me know!
- Deploying the website with Debug=False, nginx config.

## Use

- Make a account
- Upload your folder of pdbs as a zip file and add a annotation title (e.g. Correctly Folded?) and description
- The name of the pdb file is also its protein_id

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

