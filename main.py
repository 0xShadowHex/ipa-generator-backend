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
TEMPLATE_IPA = "template/template.ipa"

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

        # 1. Entpacke die IPA-Vorlage in ein temporäres Verzeichnis
        with zipfile.ZipFile(TEMPLATE_IPA, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 2. Überschreibe die Dateien mit dem neuen Inhalt
        for file_path, content in files.items():
            # Der Pfad innerhalb der IPA lautet Payload/Application.app/www/
            target_file = os.path.join(extract_path, "Payload/Application.app/www", file_path)
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            with open(target_file, "w") as f:
                f.write(content)

        # 3. Erstelle eine neue IPA-Datei aus dem modifizierten Inhalt
        final_ipa_path = os.path.join(build_path, f"{project_name}.ipa")
        shutil.make_archive(base_name=final_ipa_path.replace('.ipa', ''), format='zip', root_dir=extract_path)
        
        # shutil.make_archive hängt .zip an, also benennen wir es um
        os.rename(f"{final_ipa_path.replace('.ipa', '')}.zip", final_ipa_path)

        background_tasks.add_task(cleanup, build_path)

        return FileResponse(
            final_ipa_path,
            media_type="application/octet-stream",
            filename=f"{project_name}.ipa"
        )

    except Exception as e:
        # Im Fehlerfall aufräumen
        if 'build_path' in locals() and os.path.exists(build_path):
            cleanup(build_path)
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"status": "ok", "message": "IPA Generator Backend is running (Robust ZIP Handling)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
