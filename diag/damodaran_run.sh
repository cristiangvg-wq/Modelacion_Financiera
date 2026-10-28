pip install xlrd
mkdir -p res/dam
python scripts/actualizar_damodaran.py --salida res/dam/datos_damodaran.json > res/dam/log.txt 2>&1
