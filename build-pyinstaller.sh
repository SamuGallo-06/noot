cd src
pyinstaller --onedir --name noot \
    --distpath packages/pyinstaller/dist \
    --workpath packages/pyinstaller/work \
    --specpath packages/pyinstaler \
    --add-data "device_models.json:." \
    --add-data "assets:assets" \
    main.py