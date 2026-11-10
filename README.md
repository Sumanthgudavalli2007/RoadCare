# RoadCare – Road Damage Reporting System

## Project Overview
RoadCare is a web-based road damage reporting and tracking system designed to help citizens report road problems and help authorities monitor and prioritize repair activities.

## Technologies Used
- Python
- Flask
- HTML
- CSS
- JavaScript
- SQLite
- Leaflet Maps
- OpenStreetMap
- OpenCV (planned image-processing functionality)

## Main Features
- Citizen registration and login
- Authority login and role-based access
- Road damage reporting with photographs
- GPS location capture
- Unique report ID generation
- Report status tracking
- Interactive map integration
- Authority dashboard
- Duplicate report detection
- Severity-based priority scoring

## Project Structure
- app/ – Application modules and templates
- run.py – Application entry point
- requirements.txt – Python dependencies
- create_authority.py – Authority account setup

## Installation and Execution

1. Clone or download the repository.
2. Create a Python virtual environment.
3. Install dependencies:

`pip install -r requirements.txt`

4. Run the application:

`python run.py`

5. Open the local URL displayed in the terminal.

## Note
The database and citizen-uploaded images are stored locally and are excluded from this repository. The application should initialize its database before first use.

## Project Purpose
To improve road maintenance reporting, transparency, and communication between citizens and authorities.