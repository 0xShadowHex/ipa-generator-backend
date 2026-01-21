import os
import shutil
import zipfile
import uuid
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS erlauben
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "/tmp/ipa_builds"
# Wir verwenden nun die Application.zip als Vorlage
TEMPLATE_ZIP = "template/template.zip"

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

def cleanup(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)

@app.post("/generate-ipa")
async def generate_ipa(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        files = data.get("files", {})
        project_name = data.get("projectName", "Application")

        build_id = str(uuid.uuid4())
        build_path = os.path.join(TEMP_DIR, build_id)
        extract_path = os.path.join(build_path, "extracted")
        os.makedirs(extract_path)

        # 1. Entpacke die Vorlage
        with zipfile.ZipFile(TEMPLATE_ZIP, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 2. Überschreibe die Dateien basierend auf der analysierten Struktur
        # Die Struktur ist: Payload/Application.app/web/html/index.html, etc.
        for file_path, content in files.items():
            # Wir ordnen die Dateien den entsprechenden Unterordnern zu
            if file_path.endswith('.html'):
                target_subpath = "Payload/Application.app/web/html"
            elif file_path.endswith('.css'):
                target_subpath = "Payload/Application.app/web/css"
            elif file_path.endswith('.js'):
                target_subpath = "Payload/Application.app/web/js"
            else:
                target_subpath = "Payload/Application.app/web"

            target_file = os.path.join(extract_path, target_subpath, os.path.basename(file_path))
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content)

        # 3. Erstelle die neue IPA (ZIP)
        # WICHTIG: Wir müssen im extrahierten Verzeichnis zippen, damit 'Payload' auf der obersten Ebene liegt
        final_ipa_path = os.path.join(build_path, f"{project_name}.ipa")
        
        # Wir nutzen zipfile direkt, um volle Kontrolle über die Struktur zu haben
        with zipfile.ZipFile(final_ipa_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            for root, dirs, filenames in os.walk(extract_path):
                for filename in filenames:
                    abs_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(abs_path, extract_path)
                    new_zip.write(abs_path, rel_path)

        background_tasks.add_task(cleanup, build_path)

        return FileResponse(
            final_ipa_path,
            media_type="application/octet-stream",
            filename=f"{project_name}.ipa"
        )

    except Exception as e:
        if 'build_path' in locals() and os.path.exists(build_path):
            cleanup(build_path)
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"status": "ok", "message": "IPA Generator Backend is running (Final Path Fix)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
