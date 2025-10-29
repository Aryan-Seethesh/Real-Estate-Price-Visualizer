import sys
from datetime import datetime
from typing import List

import pandas as pd

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QListWidget, QListWidgetItem, QLineEdit, QSpinBox,
    QPushButton, QTabWidget, QFrame, QStatusBar, QDateEdit, QMessageBox, QSlider,
    QScrollArea, QGroupBox, QFormLayout, QSizePolicy
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import seaborn as sns

from db import bootstrap, seed_synthetic_listings, seed_city_synthetic, seed_missing_cities_listings
from utils import fetch_all_listings, aggregate_by_locality, monthly_trend


class MplCanvas(FigureCanvas):
    def __init__(self, width: float = 8, height: float = 5, dpi: int = 110) -> None:
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.figure)


class RealEstateQtApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Real Estate Price Visualizer — Qt")
        self.resize(1320, 860)

        # Global visual style
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background-color: #0f172a; color: #e5e7eb; }
            QLabel { color: #e5e7eb; }
            QFrame#TopBar { background-color: #111827; }
            QComboBox, QLineEdit, QSpinBox, QDateEdit { 
                background-color: #111827; color: #e5e7eb; border: 1px solid #1f2937; padding: 6px; 
            }
            QListWidget { background-color: #0b1020; color: #e5e7eb; border: 1px solid #1f2937; }
            QPushButton { background-color: #22c55e; color: #0b1020; padding: 8px 12px; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background-color: #16a34a; }
            QTabBar::tab { background: #0b1020; padding: 8px 12px; }
            QTabBar::tab:selected { background: #111827; }
            QGroupBox { border: 1px solid #1f2937; margin-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; }
            """
        )

        sns.set_theme(style="darkgrid")

        # Data/bootstrap
        self.conn = bootstrap()
        self.ensure_seeded()
        self.df = fetch_all_listings(self.conn)

        # Layout skeleton
        root = QWidget()
        root_layout = QVBoxLayout(root)
        self.setCentralWidget(root)

        # Top bar
        topbar = QFrame(objectName="TopBar")
        topbar_layout = QHBoxLayout(topbar)
        title = QLabel("Real Estate Price Visualizer")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        topbar_layout.addWidget(title)
        topbar_layout.addStretch(1)
        root_layout.addWidget(topbar)

        # Content split
        content = QWidget()
        content_layout = QHBoxLayout(content)
        root_layout.addWidget(content, 1)

        # Left filters
        # Left filters inside a scroll area for better layout and no overlap
        self.filters_panel = self._build_filters()
        scroll = QScrollArea()
        scroll.setWidget(self.filters_panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(320)
        scroll.setMaximumWidth(420)
        content_layout.addWidget(scroll, 0)

        # Right content: KPIs + tabs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        kpi_row = QHBoxLayout()
        self.kpi1 = QLabel("Median PPSF: —")
        self.kpi2 = QLabel("Localities: —")
        self.kpi3 = QLabel("Listings: —")
        for lbl in (self.kpi1, self.kpi2, self.kpi3):
            lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            kpi_row.addWidget(lbl)
            kpi_row.addSpacing(16)
        right_layout.addLayout(kpi_row)

        self.tabs = QTabWidget()
        self.tab_trend = QWidget(); self.tab_compare = QWidget(); self.tab_dist = QWidget()
        self.tabs.addTab(self.tab_trend, "Trend")
        self.tabs.addTab(self.tab_compare, "Compare")
        self.tabs.addTab(self.tab_dist, "Distributions")
        right_layout.addWidget(self.tabs, 1)

        content_layout.addWidget(right_panel, 1)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

        # Charts
        self._build_canvases()

        # Populate filters and initial render
        self._refresh_filters()
        self._run_refresh()

    # --- bootstrap helpers ---
    def ensure_seeded(self) -> None:
        try:
            seed_synthetic_listings(self.conn, listings_per_city=60)
            seed_city_synthetic(self.conn, "Navi Mumbai", listings=200)
            seed_missing_cities_listings(self.conn, listings_per_city=40)
        except Exception:
            pass

    # --- UI construction ---
    def _build_filters(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Group: Location
        loc_group = QGroupBox("Location")
        loc_form = QFormLayout(loc_group)
        loc_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.city_combo = QComboBox(); self.city_combo.currentIndexChanged.connect(self._on_city_change)
        loc_form.addRow(QLabel("City:"), self.city_combo)
        self.localities_list = QListWidget(); self.localities_list.setSelectionMode(QListWidget.MultiSelection)
        self.localities_list.setMinimumHeight(120); self.localities_list.itemSelectionChanged.connect(self._run_refresh)
        loc_form.addRow(QLabel("Localities (≤3):"), self.localities_list)
        self.types_list = QListWidget(); self.types_list.setSelectionMode(QListWidget.MultiSelection)
        self.types_list.setMinimumHeight(120); self.types_list.itemSelectionChanged.connect(self._run_refresh)
        loc_form.addRow(QLabel("Property Types:"), self.types_list)
        layout.addWidget(loc_group)

        # Group: Specs
        spec_group = QGroupBox("Specs")
        spec_form = QFormLayout(spec_group)
        self.bhk_list = QListWidget(); self.bhk_list.setSelectionMode(QListWidget.MultiSelection)
        self.bhk_list.setMinimumHeight(90); self.bhk_list.itemSelectionChanged.connect(self._run_refresh)
        spec_form.addRow(QLabel("BHK:"), self.bhk_list)
        self.min_price_edit = QLineEdit(); self.min_price_edit.setPlaceholderText("e.g. 1000000"); self.min_price_edit.returnPressed.connect(self._run_refresh)
        self.max_price_edit = QLineEdit(); self.max_price_edit.setPlaceholderText("e.g. 50000000"); self.max_price_edit.returnPressed.connect(self._run_refresh)
        spec_form.addRow(QLabel("Price Min (₹):"), self.min_price_edit)
        spec_form.addRow(QLabel("Price Max (₹):"), self.max_price_edit)
        self.min_area_edit = QLineEdit(); self.min_area_edit.setPlaceholderText("e.g. 300"); self.min_area_edit.returnPressed.connect(self._run_refresh)
        self.max_area_edit = QLineEdit(); self.max_area_edit.setPlaceholderText("e.g. 2500"); self.max_area_edit.returnPressed.connect(self._run_refresh)
        spec_form.addRow(QLabel("Area Min (sqft):"), self.min_area_edit)
        spec_form.addRow(QLabel("Area Max (sqft):"), self.max_area_edit)
        layout.addWidget(spec_group)

        # Group: Time & Quality
        time_group = QGroupBox("Time & Quality")
        time_form = QFormLayout(time_group)
        self.granularity_combo = QComboBox(); self.granularity_combo.addItems(["Monthly", "Daily"]); self.granularity_combo.currentIndexChanged.connect(self._run_refresh)
        time_form.addRow(QLabel("Granularity:"), self.granularity_combo)
        self.date_from_edit = QLineEdit(); self.date_from_edit.setPlaceholderText("YYYY-MM-DD"); self.date_from_edit.returnPressed.connect(self._run_refresh)
        self.date_to_edit = QLineEdit(); self.date_to_edit.setPlaceholderText("YYYY-MM-DD"); self.date_to_edit.returnPressed.connect(self._run_refresh)
        time_form.addRow(QLabel("Date From:"), self.date_from_edit)
        time_form.addRow(QLabel("Date To:"), self.date_to_edit)
        # Sliders row
        self.date_from_label = QLabel("—")
        self.date_to_label = QLabel("—")
        self.date_from_slider = QSlider(Qt.Orientation.Horizontal); self.date_to_slider = QSlider(Qt.Orientation.Horizontal)
        self.date_from_slider.valueChanged.connect(self._on_date_slider_change)
        self.date_to_slider.valueChanged.connect(self._on_date_slider_change)
        time_form.addRow(QLabel("Slider From:"), self.date_from_label)
        time_form.addRow(self.date_from_slider)
        time_form.addRow(QLabel("Slider To:"), self.date_to_label)
        time_form.addRow(self.date_to_slider)
        self.min_samples_spin = QSpinBox(); self.min_samples_spin.setRange(1, 100); self.min_samples_spin.valueChanged.connect(self._run_refresh)
        time_form.addRow(QLabel("Min samples / locality:"), self.min_samples_spin)
        layout.addWidget(time_group)

        # Apply button and spacer
        self.refresh_btn = QPushButton("Apply Filters"); self.refresh_btn.clicked.connect(self._run_refresh)
        self.refresh_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.refresh_btn)
        layout.addStretch(1)
        return panel

    def _build_canvases(self) -> None:
        # Trend
        trend_layout = QVBoxLayout(self.tab_trend)
        self.fig_trend = Figure(figsize=(8, 5), dpi=110); self.ax_trend = self.fig_trend.add_subplot(1, 1, 1)
        self.canvas_trend = FigureCanvas(self.fig_trend)
        trend_layout.addWidget(self.canvas_trend)

        # Compare
        compare_layout = QVBoxLayout(self.tab_compare)
        self.fig_compare = Figure(figsize=(8, 5), dpi=110); self.ax_compare = self.fig_compare.add_subplot(1, 1, 1)
        self.canvas_compare = FigureCanvas(self.fig_compare)
        compare_layout.addWidget(self.canvas_compare)

        # Distributions
        dist_layout = QVBoxLayout(self.tab_dist)
        self.fig_dist = Figure(figsize=(10, 5), dpi=110)
        self.ax_hist = self.fig_dist.add_subplot(1, 2, 1)
        self.ax_box = self.fig_dist.add_subplot(1, 2, 2)
        self.canvas_dist = FigureCanvas(self.fig_dist)
        dist_layout.addWidget(self.canvas_dist)

    # --- data/filter wiring ---
    def _refresh_filters(self) -> None:
        if self.df.empty:
            cities: List[str] = []
        else:
            cities = sorted(self.df["city"].dropna().unique().tolist())
        self.city_combo.clear(); self.city_combo.addItems(cities)
        if cities and not self.city_combo.currentText():
            self.city_combo.setCurrentIndex(0)
        self._update_dynamic_options()

        if self.df.empty:
            self.min_price_edit.setText("0.0"); self.max_price_edit.setText("1.0")
            self.min_area_edit.setText("0.0"); self.max_area_edit.setText("1.0")
            # reset date sliders disabled
            self._init_date_axis_values([])
            return
        price_min = float(self.df["total_price"].min()); price_max = float(self.df["total_price"].max())
        area_min = float(self.df["area_sqft"].min()); area_max = float(self.df["area_sqft"].max())
        if price_min == price_max:
            price_min, price_max = (0.0, price_max * 1.1) if price_max > 0 else (0.0, 1.0)
        if area_min == area_max:
            area_min, area_max = (0.0, area_max * 1.1) if area_max > 0 else (0.0, 1.0)
        self.min_price_edit.setText(f"{price_min}")
        self.max_price_edit.setText(f"{price_max}")
        self.min_area_edit.setText(f"{area_min}")
        self.max_area_edit.setText(f"{area_max}")

        # Initialize date slider domain from dataset
        try:
            dates = pd.to_datetime(self.df["listed_date"], errors="coerce").dropna().dt.date.unique().tolist()
            dates = sorted(dates)
        except Exception:
            dates = []
        self._init_date_axis_values(dates)
        # If text edits are empty, set them to full range and sync sliders
        if not self.date_from_edit.text() and dates:
            self.date_from_edit.setText(dates[0].isoformat())
        if not self.date_to_edit.text() and dates:
            self.date_to_edit.setText(dates[-1].isoformat())
        self._set_date_slider_positions_from_texts()

    def _on_city_change(self) -> None:
        self._update_dynamic_options()
        self._run_refresh()

    def _update_dynamic_options(self) -> None:
        city = self.city_combo.currentText()
        dfc = self.df
        if city:
            dfc = dfc[dfc["city"] == city]
        locs = sorted(dfc["locality"].dropna().unique().tolist())
        types = sorted(set(dfc["property_type"].dropna().unique().tolist()) | {
            "Apartment", "Penthouse", "Studio", "RK", "Villa", "Row House", "Duplex", "Triplex", "Loft", "Townhouse"
        })
        bhks = sorted([int(x) for x in dfc["bhk"].dropna().unique()])

        def set_list_items(widget: QListWidget, values: List[str]) -> None:
            widget.clear()
            for v in values:
                item = QListWidgetItem(str(v))
                widget.addItem(item)

        set_list_items(self.localities_list, locs)
        set_list_items(self.types_list, types)
        set_list_items(self.bhk_list, [str(v) for v in bhks])

    def _run_refresh(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        try:
            self.status.showMessage("Loading…")
            self.df = fetch_all_listings(self.conn)
            df = self._apply_filters(self.df)
            agg = aggregate_by_locality(df)
            if not agg.empty and "listing_count" in agg.columns:
                agg = agg[agg["listing_count"] >= int(self.min_samples_spin.value())]
            self._update_kpis(agg)
            self._draw_trend(df)
            self._draw_compare(agg)
            self._draw_hist(df)
            self._draw_box(df)
            self.canvas_trend.draw(); self.canvas_compare.draw(); self.canvas_dist.draw()
            self.status.showMessage(f"Rows: {len(df):,}")
        except Exception as e:
            self.status.showMessage("Error")
            QMessageBox.critical(self, "Error", str(e))

    def _apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        mask = pd.Series(True, index=df.index)
        city = self.city_combo.currentText()
        if city:
            mask &= df["city"] == city
        # localities (≤3)
        sel_locs = [i.text() for i in self.localities_list.selectedItems()][:3]
        if sel_locs:
            mask &= df["locality"].isin(sel_locs)
        # types
        sel_types = [i.text() for i in self.types_list.selectedItems()]
        if sel_types:
            mask &= df["property_type"].isin(sel_types)
        # bhk
        sel_bhk = []
        for i in self.bhk_list.selectedItems():
            try:
                sel_bhk.append(int(i.text()))
            except Exception:
                pass
        if sel_bhk:
            mask &= df["bhk"].isin(sel_bhk)

        try:
            pmin = float(self.min_price_edit.text() or 0); pmax = float(self.max_price_edit.text() or 1e20)
            amin = float(self.min_area_edit.text() or 0); amax = float(self.max_area_edit.text() or 1e20)
            mask &= (df["total_price"] >= pmin) & (df["total_price"] <= pmax)
            mask &= (df["area_sqft"] >= amin) & (df["area_sqft"] <= amax)
        except Exception:
            pass

        # date range
        try:
            df_dates = pd.to_datetime(df["listed_date"]) 
            if self.date_from_edit.text():
                mask &= df_dates >= pd.Timestamp(self.date_from_edit.text())
            if self.date_to_edit.text():
                mask &= df_dates <= pd.Timestamp(self.date_to_edit.text())
        except Exception:
            pass
        return df.loc[mask].copy()

    # --- date slider helpers ---
    def _init_date_axis_values(self, dates: List[object]) -> None:
        """Initialize/refresh slider range from a sorted list of date objects (datetime.date)."""
        self._date_values = dates or []
        has = len(self._date_values) > 0
        for s in (self.date_from_slider, self.date_to_slider):
            s.setEnabled(has)
            s.blockSignals(True)
            s.setMinimum(0)
            s.setMaximum(max(0, len(self._date_values) - 1))
            s.setSingleStep(1)
            s.setPageStep(7)
            s.blockSignals(False)
        # defaults
        if has:
            self.date_from_slider.setValue(0)
            self.date_to_slider.setValue(len(self._date_values) - 1)
            self.date_from_label.setText(self._date_values[0].isoformat())
            self.date_to_label.setText(self._date_values[-1].isoformat())
        else:
            self.date_from_label.setText("—")
            self.date_to_label.setText("—")

    def _set_date_slider_positions_from_texts(self) -> None:
        if not getattr(self, "_date_values", None):
            return
        try:
            tmin = pd.to_datetime(self.date_from_edit.text()).date() if self.date_from_edit.text() else None
            tmax = pd.to_datetime(self.date_to_edit.text()).date() if self.date_to_edit.text() else None
        except Exception:
            tmin = tmax = None
        if tmin in self._date_values:
            self.date_from_slider.setValue(self._date_values.index(tmin))
            self.date_from_label.setText(tmin.isoformat())
        if tmax in self._date_values:
            self.date_to_slider.setValue(self._date_values.index(tmax))
            self.date_to_label.setText(tmax.isoformat())

    def _on_date_slider_change(self) -> None:
        if not getattr(self, "_date_values", None):
            return
        i = max(0, min(self.date_from_slider.value(), len(self._date_values) - 1))
        j = max(0, min(self.date_to_slider.value(), len(self._date_values) - 1))
        if i > j:
            # keep order by snapping the one that moved
            sender = self.sender()
            if sender is self.date_from_slider:
                i = j
                self.date_from_slider.blockSignals(True); self.date_from_slider.setValue(i); self.date_from_slider.blockSignals(False)
            else:
                j = i
                self.date_to_slider.blockSignals(True); self.date_to_slider.setValue(j); self.date_to_slider.blockSignals(False)
        dmin = self._date_values[i]; dmax = self._date_values[j]
        self.date_from_label.setText(dmin.isoformat())
        self.date_to_label.setText(dmax.isoformat())
        # sync text edits and refresh
        self.date_from_edit.setText(dmin.isoformat())
        self.date_to_edit.setText(dmax.isoformat())
        self._run_refresh()

    def _update_kpis(self, agg: pd.DataFrame) -> None:
        if not agg.empty and "median_ppsf" in agg.columns:
            med = agg["median_ppsf"].median()
            locs = agg["locality"].nunique()
            listings = int(agg["listing_count"].sum()) if "listing_count" in agg.columns else 0
            self.kpi1.setText(f"Median PPSF: ₹ {med:,.0f}")
            self.kpi2.setText(f"Localities: {locs:,}")
            self.kpi3.setText(f"Listings: {listings:,}")
        else:
            self.kpi1.setText("Median PPSF: —")
            self.kpi2.setText("Localities: —")
            self.kpi3.setText("Listings: —")

    # --- plots ---
    def _draw_trend(self, df: pd.DataFrame) -> None:
        self.ax_trend.clear()
        if df.empty:
            self.ax_trend.set_title("Trend: No data")
            return
        if (self.granularity_combo.currentText() == "Daily"):
            tmp = (
                df.assign(listed_date=pd.to_datetime(df["listed_date"]).dt.date)
                  .groupby(["locality", "listed_date"], as_index=False)
                  .agg(median_ppsf=("ppsf", "median"))
            )
            xcol = "listed_date"; xlabel = "Date"
        else:
            tmp = monthly_trend(df)
            xcol = "listed_month"; xlabel = "Month"
        for loc, g in tmp.groupby("locality"):
            self.ax_trend.plot(g[xcol], g["median_ppsf"], marker="o", label=str(loc))
        self.ax_trend.set_title("Trend · Median PPSF")
        self.ax_trend.set_xlabel(xlabel)
        self.ax_trend.set_ylabel("Median PPSF")
        self.ax_trend.legend(loc="best", fontsize=8)

    def _draw_compare(self, agg: pd.DataFrame) -> None:
        self.ax_compare.clear()
        if agg.empty:
            self.ax_compare.set_title("Compare: No data")
            return
        data = agg.sort_values("median_ppsf", ascending=False).head(15)
        self.ax_compare.bar(data["locality"], data["median_ppsf"], color="#38bdf8")
        self.ax_compare.set_title("Compare · Current Median PPSF")
        self.ax_compare.set_ylabel("Median PPSF")
        self.ax_compare.tick_params(axis='x', rotation=45, labelsize=8)

    def _draw_hist(self, df: pd.DataFrame) -> None:
        self.ax_hist.clear()
        if df.empty:
            self.ax_hist.set_title("Price Distribution: No data")
            return
        self.ax_hist.hist(df["total_price"], bins=40, color="#22c55e")
        self.ax_hist.set_title("Distribution · Total Price")
        self.ax_hist.set_xlabel("Total Price (₹)")

    def _draw_box(self, df: pd.DataFrame) -> None:
        self.ax_box.clear()
        if df.empty:
            self.ax_box.set_title("PPSF Box: No data")
            return
        try:
            types = df["property_type"].astype(str)
            self.ax_box.set_title("PPSF by Property Type")
            data = [df.loc[types == t, "ppsf"].dropna().values for t in types.unique()]
            self.ax_box.boxplot(data, labels=types.unique(), patch_artist=True)
            self.ax_box.tick_params(axis='x', rotation=45, labelsize=8)
        except Exception:
            self.ax_box.set_title("PPSF by Property Type (error)")


def main() -> None:
    app = QApplication(sys.argv)
    try:
        window = RealEstateQtApp()
    except Exception as e:
        # Graceful startup error display
        m = QMessageBox()
        m.setIcon(QMessageBox.Icon.Critical)
        m.setWindowTitle("Startup Error")
        m.setText(str(e))
        m.exec()
        return
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


