import pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon
from itertools import combinations
from statsmodels.stats.multitest import multipletests
import matplotlib.pyplot as plt

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
    algorithms = ['user_total', 'generated_total', 'hybrid_total']
    pairs = list(combinations(algorithms, 2))

    p_values = []
    for a, b in pairs:
        stat, p = wilcoxon(df[a], df[b])
        # print(f"{a} vs {b} -- p = {p:.4f}")
        p_values.append(p)

    reject, pvals_corrected, _, _ = multipletests(p_values, method='bonferroni')
    for i, (a, b) in enumerate(pairs):
            print(f"{a} vs {b} (corrected p = {pvals_corrected[i]:.4f}) -> {'Significant' if reject[i] else 'N.S.'}")

def plot_overall_scores(df):

    # Boxplot of all algorithm performances
    df[['user_total', 'generated_total', 'hybrid_total']].plot.box()
    plt.title("Performance Comparison of Algorithms")
    plt.ylabel("Total induced IAC")
    plt.xticks([1, 2, 3], ['user-only', 'llm_generated', 'user+llm'])
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # Load the data
    filename = "info_cost_analysis.csv"
    df = get_formatted_df(filename)
    friedman_test(df)
    pairwise_wilcoxon(df)
    plot_overall_scores(df)