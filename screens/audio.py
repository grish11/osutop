from textual.app import ComposeResult
from textual.widgets import Header, Footer, DataTable, Static
from textual.screen import Screen
from textual import work
from screens.variableDetail import VariableDetailScreen

import shutil
import subprocess, os



# Functions -------------------------------------------
def getAudioInfo() -> dict[str, str]:
    empty = {
        "sampleRate":   "—",
        "bufferSize":   "—",
        "audioLatency": "—",
        "busyRatio":    "—",
        "waitRatio":    "—",
        "xrunCount":    "—",
    }
    if not shutil.which("pw-top"):
        return empty
    try:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        result = subprocess.run(["pw-top", "-b", "--iterations=3"],capture_output=True,text=True,timeout=5, env=env)
    except subprocess.TimeoutExpired:
        return empty

    lines = result.stdout.splitlines()

    # split into snapshots
    header = "S   ID  QUANT"
    snapshots = []
    current = []
    for line in lines:
        if line.startswith(header):
            if current:
                snapshots.append(current)
            current = []
        else:
            current.append(line)
    if current:
        snapshots.append(current)
    if not snapshots:
        return empty

    # use the most recent snapshot
    for line in snapshots[-1]:
        parts = line.split()
        if not parts or parts[0] != "R" or len(parts) < 9:
            continue
        if "+" in parts[9:] or "=" in parts[9:]:
            continue
        try:
            bufferSize = int(parts[2])
            sampleRate = int(parts[3])
            waitRatio = float(parts[6])
            busyRatio = float(parts[7])
            xrunCount = int(parts[8])
        except ValueError:
            continue

        audioLatency = (bufferSize / sampleRate) * 1000
        cpuHeadroom = (1.0 - busyRatio) * 100

        return {
            "sampleRate":   f"{sampleRate} hz",
            "bufferSize":   str(bufferSize),
            "audioLatency": f"{audioLatency:.2f} ms",
            "busyRatio":    f"{busyRatio:.2f} ({cpuHeadroom:.0f}% headroom)",
            "waitRatio":    f"{waitRatio:.2f}",
            "xrunCount":    f"{xrunCount}",
        }

    return empty


# Screens ---------------------------------------------
ROW_LABELS = [
    ("sampleRate",   "Sample Rate"),
    ("bufferSize",   "Buffer Size"),
    ("audioLatency", "Audio Latency"),
    ("busyRatio",    "B(Busy)/Q"),
    ("waitRatio",    "W(Wait)/Q"),
    ("xrunCount",    "XRUNs"),
]


class AudioLatencyScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("variable", key="variable")
        table.add_column("value **Order is not significant**", key="value")

        # seed the table with labels and initial values
        data = getAudioInfo()
        for key, label in ROW_LABELS:
            table.add_row(label, data[key], key=key)

        self.set_interval(3.5, self.refreshValues)

    @work(exclusive=True, thread=True)
    def refreshValues(self) -> None:
        data = getAudioInfo() 
        table = self.query_one(DataTable)
        for key, _ in ROW_LABELS:
            self.app.call_from_thread(table.update_cell, key, "value", data[key])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            key = event.row_key.value
            table = self.query_one(DataTable)
            currentValue = table.get_cell(event.row_key, "value")
            displayLabel = dict(ROW_LABELS)[key]
            self.app.push_screen(VariableDetailScreen(key, displayLabel, currentValue, source="audio"))
