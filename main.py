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
        
        # 1. Erstelle eine Kopie der Vorlage als .zip
        temp_zip = os.path.join(build_path, "temp.zip")
        shutil.copy(TEMPLATE_IPA, temp_zip)
        
        # 2. Dateien in das ZIP einfügen
        # Wir öffnen das ZIP im 'append' Modus
        with zipfile.ZipFile(temp_zip, 'a') as zip_ref:
            for file_path, content in files.items():
                # Der Pfad innerhalb der IPA (Payload/Application.app/www/ oder /web/)
                # Basierend auf Standard-Cordova/Capacitor Strukturen
                internal_path = f"Payload/Application.app/www/{file_path}"
                zip_ref.writestr(internal_path, content)
        
        # 3. Benenne das ZIP in .ipa um
        final_ipa = os.path.join(build_path, f"{project_name}.ipa")
        os.rename(temp_zip, final_ipa)
        
        background_tasks.add_task(cleanup, build_path)
        
        return FileResponse(
            final_ipa, 
            media_type="application/octet-stream",
            filename=f"{project_name}.ipa"
        )
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"status": "ok", "message": "IPA Generator Backend is running (Fixed ZIP Handling)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
