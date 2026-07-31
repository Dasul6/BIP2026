import os

import matplotlib

if os.environ.get("DISPLAY", "") == "" and os.name != "nt":
    matplotlib.use("Agg")

import numpy as np
import matplotlib.pyplot as plt


def generate_sample_data(num_points=100):
    """Generate sample x and y data for plotting."""
    x = np.linspace(0, 10, num_points)
    y = np.sin(x) + 0.5 * np.random.randn(num_points)
    return x, y


def plot_sample_data(x, y):
    """Plot sample data using matplotlib."""
    plt.figure(figsize=(8, 5))
    plt.plot(x, y, marker='o', linestyle='-', color='blue', label='Sample data')
    plt.title('Sample Data Plot')
    plt.xlabel('x')
    plt.ylabel('y')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    backend = matplotlib.get_backend().lower()
    if "agg" in backend:
        plt.savefig("sample_plot.png", dpi=150)
        print("Plot saved to sample_plot.png")
    else:
        plt.show()


if __name__ == '__main__':
    x_data, y_data = generate_sample_data()
    plot_sample_data(x_data, y_data)
