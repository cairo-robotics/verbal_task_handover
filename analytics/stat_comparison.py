import pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon
from itertools import combinations
from statsmodels.stats.multitest import multipletests
import matplotlib.pyplot as plt

CONDITIONS = ['user_total', 'generated_total', 'hybrid_total']

def get_formatted_df(filename):
    df = pd.read_csv(filename)
    # df.columns = [col.strip() for col in df.columns]
    df = df.pivot(index='pid', columns='report_type')
    df.columns = ['{}_{}'.format(col[1], col[0]) for col in df.columns]
    df = df.reset_index()
    return df

def friedman_test(df):
    # Perform Friedman test on the DataFrame
    stat, p = friedmanchisquare(df['user_total'], df['generated_total'], df['hybrid_total'])
    print("Friedman test statistic:", stat)
    print("Friedman test p-value:", p)

def pairwise_wilcoxon(df):
    pairs = list(combinations(CONDITIONS, 2))

    p_values = []
    for a, b in pairs:
        stat, p = wilcoxon(df[a], df[b])
        # print(f"{a} vs {b} -- p = {p:.4f}")
        p_values.append(p)

    reject, pvals_corrected, _, _ = multipletests(p_values, method='bonferroni')
    for i, (a, b) in enumerate(pairs):
            print(f"{a} vs {b} (corrected p = {pvals_corrected[i]:.4f}) -> {'Significant' if reject[i] else 'N.S.'}")
    return pairs, reject, pvals_corrected

def plot_overall_scores(df, pairs, reject, pvals_corrected):

    # Boxplot of all algorithm performances
    df[CONDITIONS].plot.box()
    plt.title("Performance Comparison of Algorithms")
    plt.ylabel("Total induced IAC")
    plt.xticks([1, 2, 3], ['user-only', 'llm_generated', 'user+llm'])
    plt.grid(True, linestyle='--', alpha=0.5)
    # plt.tight_layout()
    # plt.show()

    y_max = max(df[CONDITIONS].max())
    y_offset = 0.05
    line_height = y_max + y_offset
    h = 0.02

    # Mapping algorithm index for boxplot positions
    label_to_index = {name: i+1 for i, name in enumerate(CONDITIONS)}

    for i, ((a, b), p_val, significant) in enumerate(zip(pairs, pvals_corrected, reject)):
        x1, x2 = label_to_index[a], label_to_index[b]
        x_middle = (x1 + x2) / 2
        y = line_height + i * y_offset

        # Draw annotation lines
        plt.plot([x1, x1, x2, x2], [y, y+h, y+h, y], lw=1.5, color='black')

        # Add p-value annotation
        if significant:
            text = f"* p = {p_val:.3f}"
        else:
            text = f"n.s. (p = {p_val:.3f})"

        plt.text(x_middle, y + h + 0.005, text,
                ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    plt.show()


def plot_individual_scores(df):
    # Transpose so we can plot each data point's performance across algorithms
    data_transposed = df[CONDITIONS].T
    data_transposed.columns = [f'DP {i+1}' for i in range(len(df))]

    # Plot each data point as a line
    plt.figure(figsize=(8, 5))
    for col in data_transposed.columns:
        plt.plot(['user-only', 'llm_generated', 'user+llm'],
                data_transposed[col],
                marker='o', linestyle='-', alpha=0.7)

    plt.title("Per-Data Point Algorithm Performance")
    plt.ylabel("Total induced IAC")
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # Load the data
    filename = "info_cost_analysis.csv"
    df = get_formatted_df(filename)
    friedman_test(df)
    pairs, reject, pvals_corrected = pairwise_wilcoxon(df)
    plot_overall_scores(df, pairs, reject, pvals_corrected)
    plot_individual_scores(df)