echo "Creating virtual environment"

python -m venv .venv
.venv\Scripts\Activate
pip install --upgrade pip

echo "Installing packages"

pip install -r requirements.txt

echo "All Done! You can activate environment using command: .venv\\Scrits\\Activate"
