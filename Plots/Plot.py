import os
import locale
import colorsys
import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from scipy.stats import linregress
from matplotlib.patches import Rectangle, Circle
from matplotlib.dates import DateFormatter
from matplotlib.ticker import PercentFormatter

FORMAT_DATE = "%b/%-d/%Y"


class Plot:
    def __init__(self, dir_plot, dpi, color="") -> None:
        self.dir_plot = dir_plot
        self.dpi = dpi
        self.color = color
        self.fig = None
        self.axes = None
    
    def create_figure(self, nrows, ncols, figsize):
        self.fig, self.axes = plt.subplots(nrows, ncols, figsize=figsize)
    
    def flatten_axes(self):
        self.axes = self.axes.flatten()

    def save_figure(self, basename):
        ext = "" if basename[-4:].lower() == ".png" else ".png"
        self.fig.savefig(os.path.join(self.dir_plot, f"{basename}{ext}").replace(":", "_"), dpi=self.dpi)  # PNG
        self.fig.savefig(os.path.join(self.dir_plot, f"{basename}{ext}").replace(":", "_").replace(".png", ".pdf"), dpi=self.dpi)  # PDF
        plt.close(self.fig)

    def plot_scatter(self, xvalues, yvalues, xlabel, ylabel, title, s=10, alpha=1, facecolor="", edgecolor="none"):
        c = self.color if facecolor == "" else facecolor        
        self.setup_plot(xvalues)
        self.axes.scatter(xvalues, yvalues, s=s, c=c, alpha=alpha, edgecolor=edgecolor)
        self.set_params(ax=self.axes, xlabel=xlabel, ylabel=ylabel, title=title)
        self.minimalistic_layout(self.axes)

    def plot_line(self, xvalues, yvalues, xlabel, ylabel, title, linewidth=2.5, alpha=0.8):
        self.setup_plot(xvalues)
        self.axes.plot(xvalues, yvalues, linewidth=linewidth, color=self.color, alpha=alpha)
        self.set_params(ax=self.axes, xlabel=xlabel, ylabel=ylabel, title=title)
        self.minimalistic_layout(self.axes)
        
    def plot_histogram(self, yvalues, xlabel, title, bins=20, percentage=True, alpha=1):
        yvalues = yvalues[~np.isnan(yvalues)]
        if self.axes is None:
            self.create_figure(1, 1, (5, 5))
        if percentage:
            self.axes.hist(yvalues, weights=np.ones(len(yvalues)) / len(yvalues), bins=bins, color=self.color, alpha=alpha)
            self.axes.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))  # percentage on y-axis
        else:
            self.axes.hist(yvalues, bins=bins, color=self.color, alpha=alpha)
        #self.axes.set_yticklabels(self.axes.get_yticklabels())
        self.set_params(ax=self.axes, xlabel=xlabel, ylabel=None, title=title)
        self.minimalistic_layout(self.axes)

    def plot_grouped_histogram(self, xvalues, yvalues, colors, xlabel, title, bins=20, alpha=0.6):
        if self.axes is None:
            self.create_figure(1, 1, self.get_size(len(xvalues)))
        colors_labelled = []
        for i in range(len(yvalues)):
            values_flat = np.hstack(yvalues[i])
            values_flat = values_flat[~np.isnan(values_flat)]
            if colors[i] in colors_labelled:  # one label per color
                self.axes.hist(values_flat, weights=np.ones(len(values_flat)) / len(values_flat), bins=bins, density=True, alpha=alpha, color=colors[i])
            else:
                self.axes.hist(values_flat, weights=np.ones(len(values_flat)) / len(values_flat), bins=bins, density=True, alpha=alpha, color=colors[i], label=xvalues[i])
                colors_labelled.append(colors[i])         
        self.axes.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))  # percentage on y-axis
        self.axes.set_yticklabels(self.axes.get_yticklabels())
        self.set_params(ax=self.axes, xlabel=xlabel, ylabel=None, title=title)
        self.fig.tight_layout()
        
    def plot_boxplot(self, xvalues, yvalues, ylabel, title):
        xvalues = self.to_date(xvalues)
        xvalues, yvalues = self.sort_by_date(xvalues, yvalues)
        self.setup_plot(xvalues)
        self.axes.boxplot(
            yvalues,
            flierprops=dict(marker="o", markersize=2, markerfacecolor=self.color), 
            boxprops=dict(facecolor=self.color, color=self.color),
            capprops=dict(color=self.color),
            medianprops=dict(color=self.color),
            patch_artist=True
            )
        self.set_params(self.axes, xticklabels=xvalues, ylabel=ylabel, title=title)
        self.format_dates(self.axes, xvalues)
        self.minimalistic_layout(self.axes)

    def plot_violinplot(self, xvalues, yvalues, ylabel, title):
        xvalues = self.to_date(xvalues)
        xvalues, yvalues = self.sort_by_date(xvalues, yvalues)
        self.setup_plot(yvalues)
        for i, yvalues_these in enumerate(yvalues):  # iterate to avoid overflow
            parts = self.axes.violinplot(
                dataset=yvalues_these,
                positions=[i],
                showmeans=False,
                showextrema=False,
                showmedians=False
            )
            for pc in parts["bodies"]:
                pc.set_facecolor(self.color)
                pc.set_edgecolor(self.scale_lightness(self.color, 0.25))
                pc.set_alpha(1)
            if 0:
                for part_name in ["cquantiles"]:
                    part = parts[part_name]
                    part.set_edgecolor(self.scale_lightness(self.color, 0.5))
                    part.set_linewidth(1)
                    part.set_alpha(1)
            quartile1, medians, quartile3 = np.percentile(yvalues_these, [25, 50, 75], axis=0)
            whiskers = np.array([
                self.adjacent_values(sorted_array, q1, q3)
                for sorted_array, q1, q3 in zip([yvalues_these], [quartile1], [quartile3])])
            self.axes.scatter([i], medians, marker="o", color=self.scale_lightness(self.color, 2), s=6, zorder=3)
            self.axes.vlines([i], quartile1, quartile3, color=self.scale_lightness(self.color, 0.5), linestyle="-", lw=5)
            self.axes.vlines([i], whiskers[:, 0], whiskers[:, 1], color=self.scale_lightness(self.color, 0.5), linestyle="-", lw=2)
        self.set_params(self.axes, xticklabels=xvalues, ylabel=ylabel, title=title)
        self.format_dates(self.axes, xvalues)
        self.minimalistic_layout(self.axes)

    def plot_boxplot_with_distribution(self, xvalues, yvalues, ylabel, title):
        xvalues = self.to_date(xvalues)
        xvalues, yvalues = self.sort_by_date(xvalues, yvalues)
        xticks = np.arange(len(yvalues))
        self.setup_plot(xvalues)
        data = pd.DataFrame({
            "x": np.int16(np.hstack([np.repeat(x, len(yvalues[x])) for x in range(len(yvalues))])), 
            "y": np.float16(np.hstack(yvalues))
            })
        self.axes = sns.violinplot(
            data=data,
            x="x",
            y="y",
            hue=True, 
            hue_order=[True, False], 
            split=True,
            ax=self.axes, 
            inner=None, 
            linewidth=2
            )
        for i, violin in enumerate(self.axes.collections):
            violin.set_color(self.color if isinstance(self.color, str) else self.color[i])
            violin.set_alpha(0.5)
        self.axes.legend_ = None
        meanprops = dict(marker="o", markerfacecolor="black", markeredgecolor="black", markersize=2)
        boxplot = self.axes.boxplot(
            yvalues,
            positions=xticks,
            showfliers=False,
            showmeans=True, 
            medianprops=dict(linewidth=0), 
            meanprops=meanprops,
            widths=np.repeat(0.2, len(yvalues))
            )
        self.axes.hlines([np.median(yvalues[i]) for i in range(len(yvalues))], xmin=xticks - 0.2, xmax=xticks + 0.2, linestyle="-", linewidth=1, color="black")
        self.set_params(self.axes, xticks=xticks, xticklabels=xvalues, xlabel="", ylabel=ylabel, title=title)
        self.format_dates(self.axes, xvalues)
        self.minimalistic_layout(self.axes)

    def setup_plot(self, values):
        if self.axes is None:
            self.create_figure(1, 1, self.get_size(len(values)))

    def plot_bars(self, xvalues, height, ylabel, xlabel, title, alpha):
        xvalues = self.to_date(xvalues)  # test if dates
        self.setup_plot(xvalues)
        self.axes.bar(xvalues, height=height, color=self.color, alpha=alpha, width=float(xvalues[1] - xvalues[0]), align="center")
        self.set_params(ax=self.axes, xticks=xvalues, ylabel=ylabel, xlabel=xlabel, xticklabels=xvalues, title=title)
        self.minimalistic_layout(self.axes)

    def plot_grouped_bars(self, xvalues, yvalues, colors, ylabel, xlabel, title):
        self.setup_plot(xvalues)
        x = np.arange(len(xvalues))
        multiplier, width = 0, 0.3
        for color, yvalues_category in zip(colors, yvalues):
            offset = width * multiplier
            rects = self.axes.bar(x + offset, yvalues_category, width, color=color)
            self.axes.bar_label(rects, padding=3)
            multiplier += 1
        self.axes.set_xticks(x + width * 0.5, xvalues)
        self.set_params(self.axes, ylabel=ylabel, xlabel=xlabel, title=title)
        self.fig.set_size_inches((6, 4))
    
    def plot_regression(self, xvalues, yvalues, plot_line=True, plot_text=False, color_text="black"):
        if self.axes is None:
            self.setup_plot(xvalues)
        regression = linregress(xvalues, yvalues)
        if plot_line:
            self.axes.plot(xvalues, regression.intercept + regression.slope * xvalues, color="black", lw=1)
        if plot_text:
            regression_text = "y={0}x{1}{2}".format(np.round(regression.slope, 6), "+" if regression.intercept >= 0 else "", np.round(regression.intercept, 6))
            correlation_text = "Pearson r-value: {}".format(np.round(regression.rvalue, 2))
            self.axes.text(np.max(xvalues) * 0.7, np.max(yvalues) * 0.95, f"{regression_text}\n{correlation_text}", c=color_text)

    def add_legend(self, labels, colors, alpha=1, shape="rectangle", fontsize=12):
        symbols = []
        for c in colors:
            if shape == "rectangle":
                symbols.append(Rectangle((0,0), 1, 1, color=c, edgecolor=None))
            elif shape == "circle":
                symbols.append(Circle((0,0), 1, color=c, edgecolor=None))
            else:
                raise ValueError()
        legend = self.axes.legend(symbols, labels, framealpha=0, fontsize=fontsize)
        for lh in legend.legendHandles:
            lh.set_alpha(alpha)

    def set_params(self, ax, xlim=None, ylim=None, xticks=None, yticks=None, xticklabels=None, yticklabels=None, xlabel=None, ylabel=None, title=None):
        self._set_param(ax.set_xlim, xlim)
        self._set_param(ax.set_ylim, ylim)
        self._set_param(ax.set_xticks, xticks)
        self._set_param(ax.set_yticks, yticks)
        if xticklabels is not None:
            ax.set_xticklabels(xticklabels, rotation=self.get_xticklabel_rotation(xticklabels))  # rotation optional
        self._set_param(ax.set_yticklabels, yticklabels)
        self._set_param(ax.set_xlabel, xlabel)
        self._set_param(ax.set_ylabel, ylabel)
        self._set_param(ax.set_title, title)
    
    def minimalistic_layout(self, ax):
        self.remove_plot_boundary(ax)
        #self.remove_yticks(ax)
        #self.remove_xticks(ax)
        self.fig.tight_layout()
    
    def every_nth_xtick(self, n):
        self.axes.set_xticks(np.float32(self.axes.get_xticks())[::n])

    @staticmethod
    def to_date(xvalues):
        try:
            return [datetime.fromisoformat(date) for date in xvalues]
        except (ValueError, TypeError):
            return xvalues

    @staticmethod
    def sort_by_date(xvalues, yvalues):
        if isinstance(xvalues[0], datetime):
            argsorted = np.argsort(xvalues)
            yvalues_sorted = []
            for idx in argsorted:
                yvalues_sorted.append(yvalues[idx])
            return np.array(xvalues, dtype=object)[argsorted], yvalues_sorted
        else:
            return xvalues, yvalues

    @staticmethod
    def format_dates(ax, xvalues):
        if isinstance(xvalues[0], datetime):
            locale.setlocale(locale.LC_ALL, "en_GB.utf8")
            ax.set_xticklabels([date.strftime(FORMAT_DATE) for date in xvalues])

    @staticmethod
    def get_xticklabel_rotation(xvalues):
        return 90 if any([len(str(xvalue)) > 5 for xvalue in xvalues]) else 0

    @staticmethod
    def remove_plot_boundary(ax):
        for location in ["right", "left", "bottom", "top"]:
            ax.spines[location].set_visible(False)

    @staticmethod
    def remove_yticks(ax):
        ax.yaxis.set_ticks_position("none")

    @staticmethod
    def remove_xticks(ax):
        ax.xaxis.set_ticks_position("none")

    @staticmethod
    def _set_param(ax_with_method, value):
        if value is not None:
            ax_with_method(value)

    @staticmethod    
    def calculate_number_of_bins(values):
        return int(len(values) / 30)

    @staticmethod
    def adjacent_values(vals, q1, q3):
        upper_adjacent_value = q3 + (q3 - q1) * 1.5
        upper_adjacent_value = np.clip(upper_adjacent_value, q3, vals[-1])
        lower_adjacent_value = q1 - (q3 - q1) * 1.5
        lower_adjacent_value = np.clip(lower_adjacent_value, vals[0], q1)
        return lower_adjacent_value, upper_adjacent_value

    @staticmethod
    def scale_lightness(color, scale_l):
        rgb = matplotlib.colors.ColorConverter.to_rgb(color)
        # convert rgb to hls
        h, l, s = colorsys.rgb_to_hls(*rgb)
        # manipulate h, l, s values and return as rgb
        return colorsys.hls_to_rgb(h, min(1, l * scale_l), s = s)

    @staticmethod
    def get_size(nx):
        width = int(np.clip(nx * 0.3, 5, 12))
        return width, int(np.clip(width * 0.4, 3, 10))


if __name__ == "__main__":
    plot = Plot("", 400, color="#eb34ab")
    plot.plot_boxplot_with_distribution(np.arange(5), [np.random.normal(0, 20, size=(1000)) for i in range(5)], "Test", "Test")
