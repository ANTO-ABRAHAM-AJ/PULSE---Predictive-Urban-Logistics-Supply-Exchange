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
                      path, cmaps: dict[str, str] | None = None) -> None:
    """One map per entry in `values` ({panel title: Series indexed by zone_code})."""
    cmaps = cmaps or {}
    n = len(values)
    fig, axes = plt.subplots(1, n, figsize=(5.6 * n, 6.6))
    axes = np.atleast_1d(axes)
    for ax, (label, series) in zip(axes, values.items()):
        g = zones.merge(series.rename("value"), left_on="zone_id", right_index=True, how="left")
        outline.plot(ax=ax, color="#f0f0f0", edgecolor="#bbbbbb", linewidth=0.6)
        g.plot(ax=ax, column="value", cmap=cmaps.get(label, "YlOrRd"), edgecolor="white",
               linewidth=0.8, legend=True,
               legend_kwds={"shrink": 0.55, "label": "per weekday"})
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
                      cmap: str = "YlOrRd") -> None:
    """Rows = zones (grouped by type), columns = hour of day."""
    order = _zone_order(matrix)
    grid = matrix.pivot_table(index="zone_code", columns="hour_of_day", values=column,
                              aggfunc="sum").reindex(order).reindex(columns=range(24), fill_value=0)
    types = matrix.drop_duplicates("zone_code").set_index("zone_code")["zone_type"].reindex(order)

    fig, ax = plt.subplots(figsize=(13, 8.5))
    im = ax.imshow(grid.to_numpy(dtype=float), aspect="auto", cmap=cmap)
    ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)], fontsize=8)
    ax.set_yticks(range(len(order)), [f"{z}  ({types[z].replace('_', ' ')})" for z in order], fontsize=8)
    ax.set_xlabel("Hour of day (weekdays)")
    for i in range(1, len(order)):                      # line between zone types
        if types.iloc[i] != types.iloc[i - 1]:
            ax.axhline(i - 0.5, color="white", linewidth=2)
    fig.colorbar(im, ax=ax, shrink=0.8, label="per weekday")
    ax.set_title(title, fontsize=13, weight="bold")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
