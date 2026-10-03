"""Maps and heatmaps for the demand and supply intelligence phases."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")                     # render to files, no window needed
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
import pandas as pd                      # noqa: E402

from pulse.geo.zones import ATTRIBUTION  # noqa: E402

TYPE_ORDER = ["office", "transit_hub", "restaurant_cluster", "mixed", "residential"]


def _zone_order(matrix: pd.DataFrame) -> list[str]:
    """Zones grouped by type (in TYPE_ORDER), then by code."""
    t = matrix[["zone_code", "zone_type"]].drop_duplicates()
    t["rank"] = t["zone_type"].map({k: i for i, k in enumerate(TYPE_ORDER)})
    return t.sort_values(["rank", "zone_code"])["zone_code"].tolist()


def choropleth_panels(zones, outline, values: dict[str, pd.Series], title: str,
                      path, cmaps: dict[str, str] | None = None,
                      units: dict[str, str] | None = None) -> None:
    """One map per entry in `values` ({panel title: Series indexed by zone_code}).
    `units` sets each panel's colour-bar label (default "per weekday")."""
    cmaps = cmaps or {}
    units = units or {}
    n = len(values)
    fig, axes = plt.subplots(1, n, figsize=(5.6 * n, 6.6))
    axes = np.atleast_1d(axes)
    for ax, (label, series) in zip(axes, values.items()):
        g = zones.merge(series.rename("value"), left_on="zone_id", right_index=True, how="left")
        outline.plot(ax=ax, color="#f0f0f0", edgecolor="#bbbbbb", linewidth=0.6)
        g.plot(ax=ax, column="value", cmap=cmaps.get(label, "YlOrRd"), edgecolor="white",
               linewidth=0.8, legend=True,
               legend_kwds={"shrink": 0.55, "label": units.get(label, "per weekday")})
        vmax = g["value"].max()
        for _, r in g.iterrows():
            p = r.geometry.representative_point()
            dark = vmax and r["value"] > 0.6 * vmax          # white text on dark fills
            ax.annotate(f"{r['zone_id']}\n{r['value']:,.0f}", (p.x, p.y), ha="center", va="center",
                        fontsize=6.5, color="white" if dark else "#222222")
        ax.set_title(label, fontsize=12)
        ax.set_axis_off()
    fig.suptitle(title, fontsize=14, weight="bold")
    fig.text(0.5, 0.02, ATTRIBUTION + ". Zones: nearest-centre grouping of wards; "
             "airport (KIA) drawn as a circle, outside BBMP limits.", ha="center", fontsize=7,
             color="#666666")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def zone_hour_heatmap(matrix: pd.DataFrame, column: str, title: str, path,
                      cmap: str = "YlOrRd", center: float | None = None,
                      vmax: float | None = None, label: str = "per weekday") -> None:
    """Rows = zones (grouped by type), columns = hour of day.
    `center` gives a diverging colour scale around that value (e.g. MPI = 1)."""
    order = _zone_order(matrix)
    grid = matrix.pivot_table(index="zone_code", columns="hour_of_day", values=column,
                              aggfunc="sum").reindex(order).reindex(columns=range(24), fill_value=0)
    types = matrix.drop_duplicates("zone_code").set_index("zone_code")["zone_type"].reindex(order)

    fig, ax = plt.subplots(figsize=(13, 8.5))
    values = grid.to_numpy(dtype=float)
    norm = None
    if center is not None:
        from matplotlib.colors import TwoSlopeNorm
        top = vmax if vmax is not None else np.nanmax(values)
        norm = TwoSlopeNorm(vmin=0, vcenter=center, vmax=max(top, center + 1e-6))
        values = np.minimum(values, top)
    im = ax.imshow(values, aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)], fontsize=8)
    ax.set_yticks(range(len(order)), [f"{z}  ({types[z].replace('_', ' ')})" for z in order], fontsize=8)
    ax.set_xlabel("Hour of day (weekdays)")
    for i in range(1, len(order)):                      # line between zone types
        if types.iloc[i] != types.iloc[i - 1]:
            ax.axhline(i - 0.5, color="white", linewidth=2)
    fig.colorbar(im, ax=ax, shrink=0.8, label=label)
    ax.set_title(title, fontsize=13, weight="bold")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def stacked_shares(df: pd.DataFrame, x: str, columns: list[str], title: str, path,
                   colors: list[str] | None = None, ylabel: str = "% of online time") -> None:
    """Stacked area chart, e.g. share of partner time in each state by hour."""
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.stackplot(df[x], *[df[c].astype(float) for c in columns], labels=columns, colors=colors, alpha=0.9)
    ax.set_xlim(df[x].min(), df[x].max())
    ax.set_ylim(0, 100)
    ax.set_xticks(range(int(df[x].min()), int(df[x].max()) + 1))
    ax.set_xlabel("Hour of day (weekdays)")
    ax.set_ylabel(ylabel)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    ax.set_title(title, fontsize=13, weight="bold")
    ax.grid(axis="y", alpha=0.3)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def stacked_bars(df: pd.DataFrame, x: str, columns: list[str], title: str, path,
                 colors: list[str] | None = None, ylabel: str = "per weekday") -> None:
    """Stacked bar chart of absolute values (e.g. lost jobs by shortage type)."""
    fig, ax = plt.subplots(figsize=(12, 5.5))
    bottom = np.zeros(len(df))
    for i, c in enumerate(columns):
        vals = df[c].astype(float).to_numpy()
        ax.bar(df[x], vals, bottom=bottom, label=c, color=None if colors is None else colors[i])
        bottom += vals
    ax.set_xticks(df[x])
    ax.set_xlabel(x)
    ax.set_ylabel(ylabel)
    ax.legend(loc="upper left", frameon=False)
    ax.set_title(title, fontsize=13, weight="bold")
    ax.grid(axis="y", alpha=0.3)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def bar_chart(labels: list[str], values: list[float], title: str, path, ylabel: str,
              color: str = "#c0392b", fmt: str = "{:.1f}") -> None:
    """Simple labelled bar chart (e.g. loss rate by MPI band)."""
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, values, color=color)
    for b, v in zip(bars, values):
        ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=13, weight="bold")
    ax.grid(axis="y", alpha=0.3)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def line_panels(panels: list[tuple[str, pd.DataFrame, str, list[str]]], title: str, path,
                ylabel: str = "per hour", styles: dict[str, dict] | None = None,
                xlabel: str | None = None) -> None:
    """Stacked line charts: each panel is (panel title, frame, x column, y columns)."""
    styles = styles or {}
    fig, axes = plt.subplots(len(panels), 1, figsize=(13, 3.6 * len(panels)), squeeze=False)
    for ax, (ptitle, df, x, cols) in zip(axes[:, 0], panels):
        for c in cols:
            ax.plot(df[x], df[c].astype(float), label=c, **styles.get(c, {}))
        ax.set_title(ptitle, fontsize=11)
        ax.set_ylabel(ylabel)
        if xlabel:
            ax.set_xlabel(xlabel)
        ax.grid(alpha=0.3)
        ax.legend(loc="upper left", frameon=False, fontsize=8)
    fig.suptitle(title, fontsize=13, weight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
