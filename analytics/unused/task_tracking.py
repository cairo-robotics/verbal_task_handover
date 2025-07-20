import matplotlib.pyplot as plt

# Example data: (start_time, end_time, task)
data = [
    (0, 5, "A"),
    (5, 10, "B"),
    (10, 15, "C"),
    (15, 20, "A"),
    (20, 25, "D"),
    (25, 30, "B"),
]

# Map tasks to y-axis levels
tasks = sorted(set(task for _, _, task in data))
task_map = {task: i for i, task in enumerate(tasks)}

# Create plot data
times = [(start, end - start) for start, end, _ in data]
y_values = [task_map[task] for _, _, task in data]

# Plot
fig, ax = plt.subplots(figsize=(12, 6))

# Draw horizontal bars for each task interval
for (start, duration), y in zip(times, y_values):
    ax.broken_barh([(start, duration)], (y - 0.4, 0.8), facecolors="tab:blue")

# Add arrows for task switches
for i in range(1, len(data)):
    prev_end = data[i - 1][1]
    prev_task = data[i - 1][2]
    current_start = data[i][0]
    current_task = data[i][2]
    y_start = task_map[prev_task]
    y_end = task_map[current_task]

    # Draw arrow
    ax.annotate(
        "",  # No text
        xy=(current_start, y_end),  # Arrowhead at the new task
        xytext=(prev_end, y_start),  # Arrow tail at the previous task
        arrowprops=dict(arrowstyle="->", color="black"),
    )

# Format plot
ax.set_yticks(range(len(tasks)))
ax.set_yticklabels(tasks)
ax.set_xlabel("Time")
ax.set_ylabel("Task")
ax.set_title("Task Switching Timeline with Arrows")
ax.grid(axis="x", linestyle="--", alpha=0.7)

plt.tight_layout()
plt.show()