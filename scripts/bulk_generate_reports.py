import os
import dotenv
dotenv.load_dotenv()

from generate_hybrid_report import generate_report

def main():
    data_dir = os.environ.get('DATA_DIR')
    # report_dir = os.path.join(data_dir, 'participant_data')
    telemetry_dir = os.path.join(data_dir, 'telemetry')
    save_dir = os.path.join(data_dir, 'reports')
    report_dir = save_dir

    # for pid in range(501, 510):
    for pid in ['ari_test', 'shiv_test', 'himanshu_test', 'ys_pilot']:
        # pid = str(pid)
        print(f"Generating reports for participant {pid}...")
        # Generate both hybrid and trace-only reports
        generate_report(pid, telemetry_dir, report_dir, save_dir, mode="hybrid")
        # generate_report(pid, telemetry_dir, report_dir, save_dir, mode="trace_only")

if __name__ == "__main__":
    main()