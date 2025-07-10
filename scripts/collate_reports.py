import os

# DATA_DIR = 'path/to/your/data_dir'  # Change this to your actual data directory
OUTPUT_FILE = 'collated_reports.txt'

def collate_reports(data_dir, output_file):
    print(data_dir)
    print(output_file)
    txt_files = sorted([f for f in os.listdir(data_dir) if f.endswith('hybrid_report.txt')])
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for idx, filename in enumerate(txt_files, 1):
            file_path = os.path.join(data_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as infile:
                outfile.write(f"Report {idx}\n")
                outfile.write(infile.read())
                outfile.write('\n---\n\n')

if __name__ == '__main__':
    DATA_DIR = os.environ.get('DATA_DIR')
    input_dir = os.path.join(DATA_DIR, 'reports')
    output_file = os.path.join(DATA_DIR, OUTPUT_FILE)
    collate_reports(input_dir, output_file)