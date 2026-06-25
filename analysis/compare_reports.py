import os

reports_dir = "/media/kaleb/T7/handover_project/participant_data/reports/"
pids = ["502", "504", "505"]

for pid in pids:
    ta_path = os.path.join(reports_dir, f"{pid}_task_aware_report.txt")
    nr_path = os.path.join(reports_dir, f"{pid}_no_report_task_aware_report.txt")
    
    print(f"\n=================== PARTICIPANT {pid} ===================")
    
    if os.path.exists(ta_path):
        print(f"\n--- TASK AWARE (with User Report) ---")
        with open(ta_path, "r") as f:
            print(f.read().strip()[:800] + "\n...[truncated]")
    else:
        print(f"Task aware report not found at {ta_path}")
        
    if os.path.exists(nr_path):
        print(f"\n--- NO-REPORT TASK AWARE (without User Report) ---")
        with open(nr_path, "r") as f:
            print(f.read().strip()[:800] + "\n...[truncated]")
    else:
        print(f"No-Report Task aware report not found at {nr_path}")
