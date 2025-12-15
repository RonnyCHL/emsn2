#!/usr/bin/env python3
"""
EMSN Report Charts Module
Generates matplotlib charts for bird activity reports
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
from pathlib import Path
from datetime import datetime
import numpy as np

# EMSN color scheme
COLORS = {
    'primary': '#2E7D32',      # Forest green
    'secondary': '#1565C0',    # Blue
    'accent': '#FF8F00',       # Amber
    'background': '#FAFAFA',   # Light gray
    'text': '#212121',         # Dark gray
    'grid': '#E0E0E0',         # Light grid
    'bars': ['#2E7D32', '#43A047', '#66BB6A', '#81C784', '#A5D6A7',
             '#1565C0', '#1976D2', '#2196F3', '#42A5F5', '#64B5F6']
}

# Set default style
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.titleweight': 'bold',
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.facecolor': COLORS['background'],
    'axes.facecolor': 'white',
    'axes.edgecolor': COLORS['grid'],
    'axes.grid': True,
    'grid.color': COLORS['grid'],
    'grid.linestyle': '--',
    'grid.alpha': 0.7
})


class ReportCharts:
    """Generate charts for EMSN reports"""

    def __init__(self, output_dir: Path):
        """
        Initialize chart generator

        Args:
            output_dir: Directory to save chart images
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.generated_charts = []

    def _save_chart(self, fig, name: str, dpi: int = 150) -> Path:
        """Save chart to file and return path"""
        filepath = self.output_dir / f"{name}.png"
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight',
                    facecolor=COLORS['background'], edgecolor='none')
        plt.close(fig)
        self.generated_charts.append(filepath)
        return filepath

    def top_species_bar(self, species_data: list, title: str = "Top 10 Soorten",
                        limit: int = 10) -> Path:
        """
        Create horizontal bar chart of top species

        Args:
            species_data: List of dicts with 'name' and 'count' keys
            title: Chart title
            limit: Number of species to show
        """
        data = species_data[:limit]
        if not data:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        names = [d['name'] for d in data][::-1]  # Reverse for horizontal bars
        counts = [d['count'] for d in data][::-1]
        colors = COLORS['bars'][:len(data)][::-1]

        bars = ax.barh(names, counts, color=colors, edgecolor='white', linewidth=0.5)

        # Add count labels on bars
        for bar, count in zip(bars, counts):
            width = bar.get_width()
            ax.text(width + max(counts) * 0.01, bar.get_y() + bar.get_height()/2,
                    f'{count:,}', ha='left', va='center', fontsize=9, color=COLORS['text'])

        ax.set_xlabel('Aantal detecties')
        ax.set_title(title, pad=15)
        ax.set_xlim(0, max(counts) * 1.15)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))

        plt.tight_layout()
        return self._save_chart(fig, 'top_species')

    def hourly_activity(self, hourly_data: dict, title: str = "Activiteit per Uur") -> Path:
        """
        Create line/area chart of hourly activity

        Args:
            hourly_data: Dict with hour (0-23) as key and count as value
        """
        if not hourly_data:
            return None

        fig, ax = plt.subplots(figsize=(12, 5))

        hours = list(range(24))
        counts = [hourly_data.get(h, 0) for h in hours]

        # Area plot
        ax.fill_between(hours, counts, alpha=0.3, color=COLORS['primary'])
        ax.plot(hours, counts, color=COLORS['primary'], linewidth=2, marker='o', markersize=4)

        # Highlight sunrise/sunset periods
        ax.axvspan(5, 8, alpha=0.1, color=COLORS['accent'], label='Ochtendkoor')
        ax.axvspan(17, 20, alpha=0.1, color=COLORS['secondary'], label='Avondactiviteit')

        ax.set_xlabel('Uur van de dag')
        ax.set_ylabel('Aantal detecties')
        ax.set_title(title, pad=15)
        ax.set_xticks(hours)
        ax.set_xticklabels([f'{h:02d}:00' for h in hours], rotation=45, ha='right')
        ax.set_xlim(0, 23)
        ax.legend(loc='upper right')

        plt.tight_layout()
        return self._save_chart(fig, 'hourly_activity')

    def daily_activity(self, daily_data: list, title: str = "Activiteit per Dag") -> Path:
        """
        Create bar chart of daily activity

        Args:
            daily_data: List of dicts with 'date' and 'count' keys
        """
        if not daily_data:
            return None

        fig, ax = plt.subplots(figsize=(10, 5))

        dates = [d['date'] for d in daily_data]
        counts = [d['count'] for d in daily_data]

        # Create day names
        day_names = []
        for d in dates:
            if isinstance(d, str):
                dt = datetime.strptime(d, '%Y-%m-%d')
            else:
                dt = d
            day_names.append(dt.strftime('%a\n%d/%m'))

        bars = ax.bar(day_names, counts, color=COLORS['primary'], edgecolor='white', linewidth=0.5)

        # Add count labels on top
        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(counts) * 0.02,
                    f'{count:,}', ha='center', va='bottom', fontsize=9, color=COLORS['text'])

        ax.set_ylabel('Aantal detecties')
        ax.set_title(title, pad=15)
        ax.set_ylim(0, max(counts) * 1.15)

        plt.tight_layout()
        return self._save_chart(fig, 'daily_activity')

    def temperature_vs_activity(self, temp_data: list,
                                 title: str = "Temperatuur vs Vogelactiviteit") -> Path:
        """
        Create dual-axis chart showing temperature and bird activity

        Args:
            temp_data: List of dicts with 'date', 'temp_avg', and 'detections' keys
        """
        if not temp_data:
            return None

        fig, ax1 = plt.subplots(figsize=(12, 5))

        dates = [d['date'] for d in temp_data]
        temps = [d.get('temp_avg') or 0 for d in temp_data]
        detections = [d.get('detections', 0) for d in temp_data]

        # Day labels
        x_labels = []
        for d in dates:
            if isinstance(d, str):
                dt = datetime.strptime(d, '%Y-%m-%d')
            else:
                dt = d
            x_labels.append(dt.strftime('%a'))

        x = range(len(dates))

        # Bar chart for detections
        bars = ax1.bar(x, detections, color=COLORS['primary'], alpha=0.7, label='Detecties')
        ax1.set_ylabel('Aantal detecties', color=COLORS['primary'])
        ax1.tick_params(axis='y', labelcolor=COLORS['primary'])
        ax1.set_ylim(0, max(detections) * 1.2 if detections else 100)

        # Line chart for temperature on secondary axis
        ax2 = ax1.twinx()
        ax2.plot(x, temps, color=COLORS['accent'], linewidth=2, marker='o',
                 markersize=6, label='Temperatuur')
        ax2.set_ylabel('Temperatuur (°C)', color=COLORS['accent'])
        ax2.tick_params(axis='y', labelcolor=COLORS['accent'])

        ax1.set_xticks(x)
        ax1.set_xticklabels(x_labels)
        ax1.set_title(title, pad=15)

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

        plt.tight_layout()
        return self._save_chart(fig, 'temp_vs_activity')

    def weather_conditions(self, weather_data: dict,
                           title: str = "Activiteit per Weersomstandigheid") -> Path:
        """
        Create grouped bar chart for different weather conditions

        Args:
            weather_data: Dict with categories and their detection counts
        """
        if not weather_data:
            return None

        fig, axes = plt.subplots(1, 3, figsize=(14, 4))

        # Wind conditions
        if 'wind' in weather_data and weather_data['wind']:
            ax = axes[0]
            wind_data = weather_data['wind']
            categories = [d['category'] for d in wind_data if d['category']]
            counts = [d['detections'] for d in wind_data if d['category']]
            if categories:
                bars = ax.bar(categories, counts, color=COLORS['secondary'])
                ax.set_title('Wind', pad=10)
                ax.set_ylabel('Detecties')
                ax.tick_params(axis='x', rotation=30)
                for bar, count in zip(bars, counts):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                            f'{count:,}', ha='center', va='bottom', fontsize=8)

        # Temperature brackets
        if 'temperature' in weather_data and weather_data['temperature']:
            ax = axes[1]
            temp_data = weather_data['temperature']
            brackets = [d['bracket'] for d in temp_data if d['bracket']]
            counts = [d['detections'] for d in temp_data if d['bracket']]
            if brackets:
                bars = ax.bar(brackets, counts, color=COLORS['accent'])
                ax.set_title('Temperatuur', pad=10)
                ax.set_ylabel('Detecties')
                ax.tick_params(axis='x', rotation=30)
                for bar, count in zip(bars, counts):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                            f'{count:,}', ha='center', va='bottom', fontsize=8)

        # Rain/Dry conditions
        if 'precipitation' in weather_data:
            ax = axes[2]
            precip = weather_data['precipitation']
            categories = list(precip.keys())
            counts = list(precip.values())
            if categories:
                colors_precip = [COLORS['secondary'], COLORS['primary']][:len(categories)]
                bars = ax.bar(categories, counts, color=colors_precip)
                ax.set_title('Neerslag', pad=10)
                ax.set_ylabel('Detecties')
                for bar, count in zip(bars, counts):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                            f'{count:,}', ha='center', va='bottom', fontsize=8)

        plt.suptitle(title, fontsize=12, fontweight='bold', y=1.02)
        plt.tight_layout()
        return self._save_chart(fig, 'weather_conditions')

    def comparison_chart(self, current_data: dict, previous_data: dict,
                         title: str = "Vergelijking met Vorige Periode") -> Path:
        """
        Create comparison bar chart between two periods

        Args:
            current_data: Dict with 'label', 'detections', 'species'
            previous_data: Dict with 'label', 'detections', 'species'
        """
        if not current_data or not previous_data:
            return None

        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        labels = [previous_data.get('label', 'Vorige'), current_data.get('label', 'Huidige')]

        # Detections comparison
        ax = axes[0]
        detections = [previous_data.get('detections', 0), current_data.get('detections', 0)]
        bars = ax.bar(labels, detections, color=[COLORS['grid'], COLORS['primary']])
        ax.set_title('Detecties', pad=10)
        ax.set_ylabel('Aantal')
        for bar, count in zip(bars, detections):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{count:,}', ha='center', va='bottom', fontsize=10, fontweight='bold')

        # Calculate change percentage
        if detections[0] > 0:
            change = ((detections[1] - detections[0]) / detections[0]) * 100
            color = COLORS['primary'] if change >= 0 else '#D32F2F'
            ax.text(0.5, 0.95, f'{change:+.1f}%', transform=ax.transAxes,
                    ha='center', fontsize=11, color=color, fontweight='bold')

        # Species comparison
        ax = axes[1]
        species = [previous_data.get('species', 0), current_data.get('species', 0)]
        bars = ax.bar(labels, species, color=[COLORS['grid'], COLORS['secondary']])
        ax.set_title('Soorten', pad=10)
        ax.set_ylabel('Aantal')
        for bar, count in zip(bars, species):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{count}', ha='center', va='bottom', fontsize=10, fontweight='bold')

        # Calculate species change
        species_change = species[1] - species[0]
        color = COLORS['primary'] if species_change >= 0 else '#D32F2F'
        ax.text(0.5, 0.95, f'{species_change:+d}', transform=ax.transAxes,
                ha='center', fontsize=11, color=color, fontweight='bold')

        plt.suptitle(title, fontsize=12, fontweight='bold', y=1.02)
        plt.tight_layout()
        return self._save_chart(fig, 'comparison')

    def species_pie(self, species_data: list, title: str = "Verdeling Top Soorten",
                    limit: int = 8) -> Path:
        """
        Create pie chart of species distribution

        Args:
            species_data: List of dicts with 'name' and 'count' keys
            limit: Number of species to show (rest grouped as 'Overig')
        """
        if not species_data:
            return None

        fig, ax = plt.subplots(figsize=(8, 8))

        # Get top species and group rest
        top = species_data[:limit]
        rest_count = sum(d['count'] for d in species_data[limit:])

        names = [d['name'] for d in top]
        counts = [d['count'] for d in top]

        if rest_count > 0:
            names.append('Overig')
            counts.append(rest_count)

        colors = COLORS['bars'][:len(names)]

        wedges, texts, autotexts = ax.pie(counts, labels=names, autopct='%1.1f%%',
                                           colors=colors, startangle=90,
                                           explode=[0.02] * len(names))

        # Style the labels
        for text in texts:
            text.set_fontsize(9)
        for autotext in autotexts:
            autotext.set_fontsize(8)
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        ax.set_title(title, pad=15)

        plt.tight_layout()
        return self._save_chart(fig, 'species_pie')

    def monthly_trend(self, monthly_data: list,
                      title: str = "Maandelijkse Trend") -> Path:
        """
        Create line chart showing monthly trends

        Args:
            monthly_data: List of dicts with 'month', 'year', 'detections', 'species'
        """
        if not monthly_data:
            return None

        fig, ax1 = plt.subplots(figsize=(12, 5))

        labels = [f"{d['month']}/{d['year']}" for d in monthly_data]
        detections = [d['detections'] for d in monthly_data]
        species = [d['species'] for d in monthly_data]

        x = range(len(labels))

        # Detections line
        ax1.plot(x, detections, color=COLORS['primary'], linewidth=2,
                 marker='o', markersize=6, label='Detecties')
        ax1.fill_between(x, detections, alpha=0.2, color=COLORS['primary'])
        ax1.set_ylabel('Aantal detecties', color=COLORS['primary'])
        ax1.tick_params(axis='y', labelcolor=COLORS['primary'])

        # Species line on secondary axis
        ax2 = ax1.twinx()
        ax2.plot(x, species, color=COLORS['secondary'], linewidth=2,
                 marker='s', markersize=6, label='Soorten', linestyle='--')
        ax2.set_ylabel('Aantal soorten', color=COLORS['secondary'])
        ax2.tick_params(axis='y', labelcolor=COLORS['secondary'])

        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45, ha='right')
        ax1.set_title(title, pad=15)

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        plt.tight_layout()
        return self._save_chart(fig, 'monthly_trend')

    def get_chart_markdown(self, chart_path: Path, alt_text: str = "Chart") -> str:
        """Get markdown reference for a chart"""
        if chart_path:
            return f"![{alt_text}]({chart_path.name})\n"
        return ""

    def cleanup(self):
        """Remove all generated chart files"""
        for chart in self.generated_charts:
            if chart.exists():
                chart.unlink()
        self.generated_charts = []


# Convenience function for quick testing
def test_charts():
    """Test chart generation"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        charts = ReportCharts(Path(tmpdir))

        # Test data
        species_data = [
            {'name': 'Merel', 'count': 150},
            {'name': 'Koolmees', 'count': 120},
            {'name': 'Pimpelmees', 'count': 95},
            {'name': 'Huismus', 'count': 80},
            {'name': 'Spreeuw', 'count': 65},
        ]

        hourly_data = {h: int(50 + 30 * np.sin((h - 6) * np.pi / 12)) for h in range(24)}

        # Generate charts
        charts.top_species_bar(species_data)
        charts.hourly_activity(hourly_data)
        charts.species_pie(species_data)

        print(f"Generated {len(charts.generated_charts)} charts in {tmpdir}")
        for chart in charts.generated_charts:
            print(f"  - {chart.name}")


if __name__ == "__main__":
    test_charts()
