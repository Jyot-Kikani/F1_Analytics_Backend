from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
from .f1loader import load_session
import fastf1
from fastf1.core import Session
from fastapi import Query
from pydantic import BaseModel
import pandas as pd
from typing import Optional, List
from datetime import datetime

app = FastAPI()

# Global cache: {(year, gp, session): FastF1 Session object}
session_cache: Dict[tuple, Session] = {}

# CORS: allow local frontend dev on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://analytics-f1.vercel.app"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "F1 backend running"}

# To get the list of years available in the F1 dataset
@app.get("/api/years", response_model=List[int])
def get_years():
    current_year = datetime.now().year
    return list(range(2018, current_year + 1))

# To get the list of races for a specific year
@app.get("/api/races/{year}", response_model=List[str])
def get_races(year: int):
    try:
        schedule = fastf1.get_event_schedule(year)
        schedule = schedule[["EventName"]]
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid year or data unavailable")

    return list(schedule['EventName'].unique())

# To get the list of sessions for a specific event
@app.get("/api/sessions/{year}/{gp}", response_model=List[str])
def get_sessions(year: int, gp: str):
    event = fastf1.get_event(year, gp)
    event = event[["Session1", "Session2", "Session3", "Session4", "Session5"]]
    return event.dropna().values.flatten().tolist()


class DriverInfo(BaseModel):
    abbreviation: str
    full_name: str
    team: str
    team_color: str
    headshot_url: Optional[str] = None

@app.get("/api/drivers/{year}/{gp}/{session}", response_model=List[DriverInfo])
def get_drivers(year: int, gp: str, session: str):
    try:
        sess = get_or_load_session(year, gp, session)
        drivers_info = []
        
        # Use results data instead of laps
        for _, driver_result in sess.results.iterrows():
                abbr = driver_result['Abbreviation']
                
                # Create driver info object
                driver_info = DriverInfo(
                    abbreviation=abbr,
                    full_name=driver_result['FullName'] if 'FullName' in driver_result else abbr,
                    team=driver_result['TeamName'] if 'TeamName' in driver_result else "Unknown",
                    team_color=("#" + driver_result['TeamColor']) if 'TeamColor' in driver_result else "#FFFFFF",
                    headshot_url=driver_result['HeadshotUrl'] if 'HeadshotUrl' in driver_result else None
                )
                drivers_info.append(driver_info)
        
        return sorted(drivers_info, key=lambda x: x.team)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load session: {str(e)}")



class DriverRequest(BaseModel):
    drivers: List[str]


@app.get("/api/laptimes/{year}/{gp}/{session}")
def get_laptimes(year: int, gp: str, session: str, drivers: str = Query("")):
    try:
        # Split comma-separated drivers string into a list
        driver_list = drivers.split(",") if drivers else []
        
        if not driver_list:
            return {}
            
        sess = get_or_load_session(year, gp, session)
        laps = sess.laps
        result = {}

        for driver in driver_list:
            dr_laps = laps[laps['Driver'] == driver]
            if dr_laps.empty:
                continue

            result[driver] = [
                {
                    "lap_num": int(row["LapNumber"]),
                    "time": row["LapTime"].total_seconds() if not pd.isnull(row["LapTime"]) else None
                }
                for _, row in dr_laps.iterrows()
                if not pd.isnull(row["LapTime"])
            ]

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing lap times: {str(e)}")
    
def get_or_load_session(year: int, gp: str, session: str) -> Session:
    key = (year, gp.lower(), session.lower())
    if key not in session_cache:
        sess = fastf1.get_session(year, gp, session)
        sess.load()
        session_cache[key] = sess
    return session_cache[key]