import onnxruntime as ort
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

def sample_uniform_sphere(num_samples):
    """Sample uniformly from S^2 (3D unit sphere) using spherical coordinates"""
    # Sample theta uniformly from [0, 2π] and cos(phi) uniformly from [-1, 1]
    theta = np.random.uniform(0, 2*np.pi, num_samples)
    cos_phi = np.random.uniform(-1.0, -0.5, num_samples)
    phi = np.arccos(cos_phi)

    # Convert to Cartesian coordinates
    x = np.sin(phi) * np.cos(theta)
    y = np.sin(phi) * np.sin(theta)
    z = np.cos(phi)

    return np.column_stack([x, y, z])

def sample_uniform_circle(num_samples):
    """Sample uniformly from S^1 (unit circle)"""
    theta = np.random.uniform(0.0, 0.0, num_samples)
    return np.column_stack([np.cos(theta), np.sin(theta)])

def analyze_policy_onnx():
    # Read the ONNX file using pathlib
    model_path = Path("policy_latest.onnx")

    if not model_path.exists():
        print(f"Error: {model_path} does not exist")
        return

    # Load ONNX model
    try:
        session = ort.InferenceSession(str(model_path))
        print(f"Model loaded successfully from {model_path}")

        # Get input and output info
        input_info = session.get_inputs()[0]
        output_info = session.get_outputs()[0]

        print(f"Input name: {input_info.name}")
        print(f"Input shape: {input_info.shape}")
        print(f"Output name: {output_info.name}")
        print(f"Output shape: {output_info.shape}")

    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # Generate input data with proper manifold sampling
    num_samples = 1000

    # First 9 dimensions: Euclidean space (sample uniformly from [-1, 1])
    euclidean_part = np.random.uniform(-0.1, 0.1, (num_samples, 9))
    #euclidean_part[:,0:3] = np.zeros((num_samples,3))
    # Dimensions 10-12 (3 dims): S^2 - 3D unit sphere
    sphere_part = sample_uniform_sphere(num_samples)

    # Dimensions 13-14 (2 dims): S^1 - first unit circle
    circle_part1 = sample_uniform_circle(num_samples)

    circle_part2 = sample_uniform_circle(num_samples)
    # # Dimensions 15-16 (2 dims): S^1 - second unit circle
    # circle_part2 = np.zeros_like(circle_part1)
    # circle_part2[:, 0] = 1.0

    # circle_part1 = np.zeros_like(circle_part1)
    # circle_part1[:, 0] = 1.0
    # sphere_part = np.zeros_like(sphere_part)
    # sphere_part[:, 2] = -1.0

    # Combine all parts
    input_data = np.column_stack([euclidean_part, sphere_part, circle_part1, circle_part2]).astype(np.float32)

    print(f"Generated {num_samples} input samples with proper manifold sampling:")
    print(f"  - First 9 dims: Euclidean space [-1, 1]")
    print(f"  - Dims 10-12: S^2 (3D unit sphere)")
    print(f"  - Dims 13-14: S^1 (unit circle)")
    print(f"  - Dims 15-16: S^1 (unit circle)")

    # Run inference
    outputs = []
    try:
        for i in range(num_samples):
            input_sample = input_data[i:i+1]  # Shape (1, 16)
            result = session.run(None, {input_info.name: input_sample})
            outputs.append(result[0][0])  # Shape (4,)

        outputs = np.array(outputs)  # Shape (1000, 4)
        print(f"Generated outputs with shape: {outputs.shape}")

    except Exception as e:
        print(f"Error during inference: {e}")
        return

    # Create subplots (2,2) to show output distributions
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Policy ONNX Output Distributions', fontsize=16)

    # Flatten axes for easier iteration
    axes = axes.flatten()

    # Plot distribution for each output dimension
    for i in range(4):
        ax = axes[i]

        # Calculate histogram
        counts, bins, patches = ax.hist(outputs[:, i], bins=50, alpha=0.7, density=True, edgecolor='black')

        # Add yellow shaded area for [-1, 1] range
        ax.axvspan(-1, 1, alpha=0.3, color='yellow', label='[-1, 1] range')

        # Calculate density within [-1, 1] range
        mask = (outputs[:, i] >= -1) & (outputs[:, i] <= 1)
        samples_in_range = np.sum(mask)
        total_samples = len(outputs[:, i])
        proportion_in_range = samples_in_range / total_samples

        # Calculate density contribution from [-1, 1] range
        range_width = 2  # 1 - (-1) = 2
        density_in_range = proportion_in_range / range_width

        ax.set_title(f'Output {i}')
        ax.set_xlabel('Value')
        ax.set_ylabel('Density')
        ax.grid(True, alpha=0.3)
        ax.legend()

        # Add statistics text with [-1, 1] density information
        mean_val = np.mean(outputs[:, i])
        std_val = np.std(outputs[:, i])
        text_str = f'μ={mean_val:.3f}\nσ={std_val:.3f}\n[-1,1] density={density_in_range:.4f}'

        ax.text(0.05, 0.95, text_str,
                transform=ax.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        # Add density label on the yellow area
        ax.text(0, ax.get_ylim()[1] * 0.7, f'ρ={density_in_range:.3f}',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.6),
                ha='center', va='center', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig('policy_output_distributions.png', dpi=300, bbox_inches='tight')
    plt.show()

    # Print summary statistics
    print("\nSummary Statistics:")
    print("-" * 50)
    for i in range(4):
        mean_val = np.mean(outputs[:, i])
        std_val = np.std(outputs[:, i])
        min_val = np.min(outputs[:, i])
        max_val = np.max(outputs[:, i])
        print(f"Output {i}: Mean={mean_val:.4f}, Std={std_val:.4f}, Min={min_val:.4f}, Max={max_val:.4f}")

if __name__ == "__main__":
    analyze_policy_onnx()
