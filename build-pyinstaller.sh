pyinstaller --onedir --name noot \
    --distpath packages/pyinstaller/dist \
    --workpath packages/pyinstaller/work \
    --specpath packages/pyinstaller \
    --add-data "../../src/device_models.json:." \
    --add-data "../../src/assets:assets" \
    --recursive-copy-metadata pymobiledevice3 \
    src/main.py