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
- The ability to see an overview of the annotations of another user

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

