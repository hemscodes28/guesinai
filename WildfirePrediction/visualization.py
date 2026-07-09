# Live animation + plots
# Code will be pasted here by the user.
"""
=========================================================
visualization.py

Visualize Continuous Wildfire Spread Simulation

Outputs
-------
1. Fire Arrival Time Map
2. Fire Centroid Trajectory
3. Animated Fire Spread GIF
4. Fire Growth Curve
=========================================================
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd
try:
    from IPython.display import HTML
except ImportError:
    def HTML(x):
        return x



class FireVisualizer:

    def __init__(self, history_df, centroid_df, ignite_t):

        self.history = history_df
        self.centroid = centroid_df
        self.ignite_t = ignite_t

    # -----------------------------------------------------
    # Fire Arrival Time Map
    # -----------------------------------------------------

    def plot_arrival_time(self):

        plt.figure(figsize=(7,6))

        img = plt.imshow(
            self.ignite_t,
            origin="upper",
            cmap="inferno"
        )

        plt.contour(
            self.ignite_t,
            levels=10,
            colors="white",
            linewidths=0.6
        )

        plt.title("Fire Arrival Time Map")

        plt.colorbar(
            img,
            label="Minutes Since Ignition"
        )

        plt.tight_layout()

        plt.savefig(
            "fire_arrival_time.png",
            dpi=300
        )

        plt.show()

    # -----------------------------------------------------
    # Fire Centroid Path
    # -----------------------------------------------------

    def plot_centroid(self):

        plt.figure(figsize=(7,6))

        plt.plot(

            self.centroid["lon"],
            self.centroid["lat"],

            "-o",

            color="firebrick",

            linewidth=2,

            markersize=4

        )

        plt.xlabel("Longitude")
        plt.ylabel("Latitude")

        plt.title("Fire Centroid Trajectory")

        plt.grid(True)

        plt.tight_layout()

        plt.savefig(
            "fire_centroid.png",
            dpi=300
        )

        plt.show()

    # -----------------------------------------------------
    # Fire Growth
    # -----------------------------------------------------

    def plot_growth(self):

        plt.figure(figsize=(8,5))

        plt.plot(

            self.centroid["t_min"],
            self.centroid["n_burning"],

            color="darkred",

            linewidth=2

        )

        plt.xlabel("Simulation Time (minutes)")
        plt.ylabel("Burning Cells")

        plt.title("Wildfire Growth")

        plt.grid(True)

        plt.tight_layout()

        plt.savefig(
            "fire_growth.png",
            dpi=300
        )

        plt.show()

    # -----------------------------------------------------
    # Fire Radius
    # -----------------------------------------------------

    def plot_radius(self):

        plt.figure(figsize=(8,5))

        plt.plot(

            self.centroid["t_min"],
            self.centroid["spread_radius_m"],

            color="orange",

            linewidth=2

        )

        plt.xlabel("Simulation Time (minutes)")
        plt.ylabel("Spread Radius (m)")

        plt.title("Wildfire Spread Radius")

        plt.grid(True)

        plt.tight_layout()

        plt.savefig(
            "fire_radius.png",
            dpi=300
        )

        plt.show()

    # -----------------------------------------------------
    # Fire Animation
    # -----------------------------------------------------

    def animate(self,
                filename="fire_spread_live.gif",
                fps=8):

        frames = sorted(self.history.t_min.unique())

        fig, ax = plt.subplots(figsize=(6,6))

        scatter = ax.scatter(
            [],
            [],
            s=8,
            c=[],
            cmap="inferno",
            vmin=0,
            vmax=max(frames)
        )

        ax.set_xlim(

            self.history.lon.min()-0.0002,
            self.history.lon.max()+0.0002

        )

        ax.set_ylim(

            self.history.lat.min()-0.0002,
            self.history.lat.max()+0.0002

        )

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

        title = ax.set_title("Time = 0 min")

        def update(frame):

            subset = self.history[
                self.history.t_min <= frame
            ]

            scatter.set_offsets(

                subset[
                    ["lon","lat"]
                ].values

            )

            scatter.set_array(

                subset["t_min"].values

            )

            title.set_text(

                f"Simulation Time = {frame:.0f} min"

            )

            return scatter, title

        ani = animation.FuncAnimation(

            fig,

            update,

            frames=frames,

            interval=100,

            repeat=True

        )

        ani.save(

            filename,

            writer="pillow",

            fps=fps

        )

        plt.close(fig)

        print("Animation Saved Successfully")

        return HTML(
            ani.to_jshtml()
        )

    # -----------------------------------------------------
    # Complete Report
    # -----------------------------------------------------

    def generate_all(self):

        self.plot_arrival_time()

        self.plot_centroid()

        self.plot_growth()

        self.plot_radius()

        self.animate()

        print("\nVisualization Completed Successfully")