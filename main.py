import io
import os
import pandas as pd
from nicegui import ui
from supabase import create_client, Client

# ==================================================
# RENDER & SUPABASE CONNECTION SETUP
# ==================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "YOUR_SUPABASE_KEY")

if not SUPABASE_URL or "YOUR_SUPABASE" in SUPABASE_URL:
    print("Warning: Ensure SUPABASE_URL and SUPABASE_KEY environment variables are set.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================================================
# CONSTANTS & TABLES
# ==================================================
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIODS = [1, 2, 3, 4, 5, 6, 7]

TABLE_FACULTY = "faculty"
TABLE_SUBJECTS = "subjects"
TABLE_CLASSES = "classes"
TABLE_TEACHING = "teaching_load"
TABLE_TIMETABLE = "timetable"

# ==================================================
# DATA HELPERS
# ==================================================
def fetch_table(table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data or []
    except Exception as e:
        ui.notify(f"Error fetching {table_name}: {e}", type="negative")
        return []

def load_timetable_data():
    return fetch_table(TABLE_TIMETABLE)

# Initialize in-memory state
timetable_records = load_timetable_data()
classes_data = fetch_table(TABLE_CLASSES)
teaching_data = fetch_table(TABLE_TEACHING)

classes_list = sorted(list(set(r.get("class_id", r.get("Class_ID", "")) for r in classes_data if r.get("class_id") or r.get("Class_ID")))) or ["CSE-A", "CSE-B"]

# ==================================================
# NICEGUI UI LAYOUT
# ==================================================
ui.query('body').classes('bg-slate-50 p-6')

ui.label("Timetable Generative System – Department of BS&H").classes("text-3xl font-bold text-slate-800 mb-1")
ui.label("☁️ Live updates synced directly with Supabase").classes("text-sm text-slate-500 mb-6")

with ui.row().classes("w-full gap-6 mb-6"):
    # Add Entry Form
    with ui.card().classes("flex-1 p-4 shadow-md bg-white rounded-lg"):
        ui.label("➕ Add Timetable Entry").classes("text-lg font-bold mb-3 text-blue-600")
        
        cls_select = ui.select(classes_list, label="Select Class", value=classes_list[0] if classes_list else None).classes("w-full mb-2")
        
        # Get subjects for selected class
        def get_subjects_for_cls(cls_val):
            subs = [r.get("subject_id", r.get("Subject_ID", "")) for r in teaching_data if str(r.get("class_id", r.get("Class_ID", ""))).upper() == str(cls_val).upper()]
            if "WEEKLY TEST" not in subs:
                subs.append("WEEKLY TEST")
            return [s for s in subs if s]

        sub_select = ui.select(get_subjects_for_cls(cls_select.value), label="Select Subject").classes("w-full mb-2")
        cls_select.on_value_change(lambda e: sub_select.set_options(get_subjects_for_cls(e.value)))

        day_select = ui.select(DAYS, label="Day", value=DAYS[0]).classes("w-full mb-2")
        period_select = ui.select(PERIODS, label="Start Period", value=PERIODS[0]).classes("w-full mb-4")

        async def add_entry():
            if not cls_select.value or not sub_select.value:
                ui.notify("Please select both Class and Subject.", type="warning")
                return

            entry = {
                "class_id": cls_select.value,
                "subject": sub_select.value,
                "day": day_select.value,
                "period": int(period_select.value),
                "room": "R101"
            }

            try:
                supabase.table(TABLE_TIMETABLE).insert(entry).execute()
                ui.notify("Successfully saved to Supabase!", type="positive")
                refresh_grid()
            except Exception as e:
                ui.notify(f"Failed to insert record: {e}", type="negative")

        ui.button("ADD ENTRY", on_click=add_entry).classes("bg-blue-600 text-white w-full py-2 rounded-md font-semibold")

    # Delete Entry Form
    with ui.card().classes("flex-1 p-4 shadow-md bg-white rounded-lg"):
        ui.label("❌ Delete Timetable Entry").classes("text-lg font-bold mb-3 text-red-600")
        
        d_cls_select = ui.select(classes_list, label="Select Class", value=classes_list[0] if classes_list else None).classes("w-full mb-2")
        d_day_select = ui.select(DAYS, label="Select Day", value=DAYS[0]).classes("w-full mb-2")
        d_period_select = ui.select(PERIODS, label="Select Period", value=PERIODS[0]).classes("w-full mb-4")

        async def delete_entry():
            try:
                supabase.table(TABLE_TIMETABLE).delete().match({
                    "class_id": d_cls_select.value,
                    "day": d_day_select.value,
                    "period": int(d_period_select.value)
                }).execute()
                ui.notify("Entry deleted from Supabase.", type="info")
                refresh_grid()
            except Exception as e:
                ui.notify(f"Delete failed: {e}", type="negative")

        ui.button("DELETE ENTRY", on_click=delete_entry).classes("bg-red-600 text-white w-full py-2 rounded-md font-semibold")

# ==================================================
# AG-GRID DISPLAY
# ==================================================
ui.label("📘 Timetable Overview").classes("text-xl font-bold mb-3 text-slate-800")

view_cls = ui.select(classes_list, value=classes_list[0] if classes_list else None, label="View Schedule For Class").classes("w-72 mb-4")

def build_grid_data(selected_class):
    records = load_timetable_data()
    # Initialize blank timetable matrix
    matrix = {day: {p: "" for p in PERIODS} for day in DAYS}

    for r in records:
        c_id = r.get("class_id", r.get("Class", ""))
        if str(c_id).upper() == str(selected_class).upper():
            day = r.get("day", r.get("Day"))
            period = int(r.get("period", r.get("Period", 0)))
            if day in DAYS and period in PERIODS:
                matrix[day][period] = f"{r.get('subject', '')}"

    rows = []
    for day in DAYS:
        row = {"day": day}
        for p in PERIODS:
            row[f"p{p}"] = matrix[day][p]
        rows.append(row)
    return rows

grid = ui.aggrid({
    "columnDefs": [
        {"field": "day", "headerName": "Day / Period", "pinned": "left", "width": 130},
        {"field": "p1", "headerName": "Period 1", "editable": True},
        {"field": "p2", "headerName": "Period 2", "editable": True},
        {"field": "p3", "headerName": "Period 3", "editable": True},
        {"field": "p4", "headerName": "Period 4", "editable": True},
        {"field": "p5", "headerName": "Period 5", "editable": True},
        {"field": "p6", "headerName": "Period 6", "editable": True},
        {"field": "p7", "headerName": "Period 7", "editable": True},
    ],
    "rowData": build_grid_data(view_cls.value),
}).classes("h-72 w-full bg-white shadow-md rounded-lg mb-4")

def refresh_grid():
    grid.options["rowData"] = build_grid_data(view_cls.value)
    grid.update()

view_cls.on_value_change(lambda _: refresh_grid())

ui.button("🔄 Refresh Data from Supabase", on_click=refresh_grid).classes("bg-slate-700 text-white px-4 py-2 rounded-md")

# Bind host port dynamically for Render
port = int(os.environ.get("PORT", 8080))
ui.run(host="0.0.0.0", port=port, title="Timetable System")
