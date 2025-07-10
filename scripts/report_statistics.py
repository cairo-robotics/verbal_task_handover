from collections import Counter
import os
import pandas as pd

def count_words_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    words = text.split()
    return len(words)

def collect_word_counts(folder_path):
    data = {}
    for filename in os.listdir(folder_path):
        if filename.endswith('report.txt'):
            try:
                pid, condition = filename.split('_', 1)
                condition = condition.replace('.txt', '')
            except ValueError:
                continue  # skip files not matching the pattern
            filepath = os.path.join(folder_path, filename)
            word_count = count_words_in_file(filepath)
            if pid not in data:
                data[pid] = {}
            data[pid][condition] = word_count
    df = pd.DataFrame.from_dict(data, orient='index')
    df.index.name = 'participant_id'
    return df

# Example usage:
# folder = '/path/to/txt/files'
# df = collect_word_counts(folder)
# print(df)

if __name__ == "__main__":
    folder = os.environ.get('DATA_DIR')
    generated_folder = os.path.join(folder, 'processed_output', 'generated_reports')
    df_generated = collect_word_counts(generated_folder)
    participant_folder = os.path.join(folder, 'participant_data')
    df_participant = collect_word_counts(participant_folder)
    full_df = pd.merge(df_generated, df_participant, how='outer', left_index=True, right_index=True, suffixes=('_generated', '_participant'))
    full_df.to_csv(os.path.join(folder, 'report_data.csv'), index=True)