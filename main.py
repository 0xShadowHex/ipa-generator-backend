import os
import shutil
import zipfile
import uuid
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS erlauben, damit das Frontend darauf zugreifen kann
# Wir erlauben alle Origins, Methoden und Header, um NetworkErrors zu vermeiden
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
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

@app.post("/generate-ipa")
async def generate_ipa(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        files = data.get("files", {})
        project_name = data.get("projectName", "Application")
        
        build_id = str(uuid.uuid4())
        build_path = os.path.join(TEMP_DIR, build_id)
        os.makedirs(build_path)
        
        # Kopiere Vorlage
        target_ipa = os.path.join(build_path, f"{project_name}.ipa")
        shutil.copy(TEMPLATE_IPA, target_ipa)
        
        # Dateien in IPA aktualisieren
        with zipfile.ZipFile(target_ipa, 'a') as zip_ref:
            # files ist ein Objekt mit { "html/index.html": "content", ... }
            for file_path, content in files.items():
                # In der IPA liegen die Web-Dateien unter Payload/Application.app/web/
                # Wir müssen den Pfad entsprechend anpassen
                internal_path = f"Payload/Application.app/web/{file_path}"
                zip_ref.writestr(internal_path, content)
                
        background_tasks.add_task(cleanup, build_path)
        
        return FileResponse(
            target_ipa, 
            media_type="application/octet-stream",
            filename=f"{project_name}.ipa"
        )
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"status": "ok", "message": "IPA Generator Backend is running with CORS enabled"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
