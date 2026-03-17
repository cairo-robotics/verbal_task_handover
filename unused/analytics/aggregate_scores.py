import os
import json
import pandas as pd

from process_states import process_bulk_saves

participant_files = ["participants_p1.csv", "participants_p2.csv"]
output_csv = "output.csv"

def read_participant_file(file_path):
    try:
        df = pd.read_csv(file_path)
        return df
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return pd.DataFrame()
    
def merge_participant_files(data_dir):
    p1_df = read_participant_file(os.path.join(data_dir, participant_files[0]))
    p2_df = read_participant_file(os.path.join(data_dir, participant_files[1]))

    if p1_df.empty or p2_df.empty:
        print("One of the participant files is empty or missing.")
        return pd.DataFrame()
    
    merged_df = pd.merge(p1_df, p2_df, on="PID", suffixes=("_p1", "_p2"))
    merged_df.drop(columns=["Visit 1 Experimenter", "Visit 2 Experimenter", "Experimenter"], inplace=True)
    merged_df.rename(columns={"Date": "p2_date"}, inplace=True)

    return merged_df

def read_meta_score(pid, data_dir):
    participant_data_file = os.path.join(data_dir, f"{pid}_save_output.json")
    try:
        with open(participant_data_file, "r") as f:
            data = json.load(f)
            return data.get("meta_score", None)
    except FileNotFoundError:
        print(f"File not found: {participant_data_file}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON from file: {participant_data_file}")
        return None
    
def process_state_data(data_dir, participant_df):
    pids_to_process = []
    for index, row in participant_df.iterrows():
        if not pd.isna(row["Visit 1 date"]):
            pid = row["PID"]
            pids_to_process.append(pid)
        if not pd.isna(row["Visit 2 date"]):
            pid = str(row["PID"]) + "_1"
            pids_to_process.append(pid)
        if not pd.isna(row["Date"]):
            pid = row["p2_PID"]
            pids_to_process.append(pid)

    process_bulk_saves(pids_to_process, os.path.join(data_dir, "participant_data"), os.path.join(data_dir, "processed_output"))

def merge_survey_data(data_dir, participant_df):
    survey_1, survey_2 = ["survey_visit_1.csv", "survey_visit_2.csv"]
    survey_1_df = pd.read_csv(os.path.join(data_dir, survey_1))
    survey_1_df.drop(columns="Timestamp", inplace=True)
    survey_1_df.columns = ["PID", "mentally_demanding", "hurried", "successful", "hard_work", "understood", "all_relevant_info", "difficulty_remembering", "resume_task_me", "resume_task_others"]
    survey_1_df.replace("1 (Very low)", 1, inplace=True)
    survey_1_df.replace("7 (Very high)", 7, inplace=True)
    survey_1_df.replace("1 (Strongly disagree)", 1, inplace=True)
    survey_1_df.replace("7 (Strongly agree)", 7, inplace=True)


    survey_2_df = pd.read_csv(os.path.join(data_dir, survey_2))
    survey_2_df.drop(columns="Timestamp", inplace=True)
    survey_2_df.columns = ["PID", "mentally_demanding", "hurried", "successful", "hard_work", "understood", "helped_completion", "easy_to_understand", "confusing", "missing_info"]
    survey_2_df.replace("1 (Very low)", 1, inplace=True)
    survey_2_df.replace("7 (Very high", 7, inplace=True)
    survey_2_df.replace("1 (Strongly disagree)", 1, inplace=True)
    survey_2_df.replace("7 (Strongly agree", 7, inplace=True)

    participant_df = pd.merge(participant_df, survey_1_df, on="PID", how="left")
    participant_df = pd.merge(participant_df, survey_2_df, on="PID", how="left", suffixes=("_v1", "_v2"))
    participant_df = pd.merge(participant_df, survey_2_df, left_on="p2_PID", right_on="PID", how="left", suffixes=("", "_p2"))
    participant_df.drop(columns=["PID_p2"], inplace=True)
    return participant_df
    

def main(data_dir, participant_df):
    data_df = pd.DataFrame(columns=["PID", "r1_score", "r2_score", "r3_score"])
    participant_df.reset_index(drop=True, inplace=True)
    for index, row in participant_df.iterrows():
        pid=row["PID"]
        r1_score = pd.NA
        r2_score = pd.NA
        r3_score = pd.NA

        if not pd.isna(row["Visit 1 date"]):
            r1_score = read_meta_score(pid, data_dir)
        if not pd.isna(row["Visit 2 date"]):
            r2_score = read_meta_score(str(pid) + "_1", data_dir)
        if not pd.isna(row["p2_date"]):
            r3_score = read_meta_score(row["p2_PID"], data_dir)

        data_df.loc[index] = [pid, r1_score, r2_score, r3_score]

    output_df = pd.merge(data_df, participant_df, on="PID", how="right")
    output_df.to_csv(os.path.join(data_dir, output_csv), index=False)

if __name__ == "__main__":
    # Get the current directory
    main_data_dir = os.environ.get("DATA_DIR")
    data_directory = os.path.join(main_data_dir, "processed_output")
    raw_data_directory = os.path.join(main_data_dir, "participant_data")

    participant_df = merge_participant_files(raw_data_directory)
    participant_df = merge_survey_data(raw_data_directory, participant_df)
    # process_state_data(main_data_dir, participant_df)
    main(data_directory, participant_df)