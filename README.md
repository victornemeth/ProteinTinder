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

## Features

- 🧬 Interactive 3D protein viewer
- 📱 Touch and mouse swipe support
- 🔐 User authentication (login/signup)
- 💾 Annotation history saved per user
- 🔁 Auto-load next unannotated protein

## Tech Stack

- Python / Django
- MySQL
- HTML / JS / 3Dmol.js
- Docker (optional)

## Run Locally

```bash
git clone https://github.com/victornemeth/ProteinTinder.git
cd ProteinTinder
docker compose up -d --build


