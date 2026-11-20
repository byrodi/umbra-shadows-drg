"""Average FPS and 1% low from PresentMon captures.

Record (admin terminal, game already in the scene to measure):
  presentmon --process_name FSD-Win64-Shipping.exe --v1_metrics --timed 120 --terminate_after_timed --output_file run1.csv

Usage: python fps_stats.py run1.csv run2.csv run3.csv
"1% low" is the average FPS over the slowest 1% of frames.
"""
import csv
import sys


def stats(path):
    with open(path, newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))
    column = "msBetweenPresents" if rows and "msBetweenPresents" in rows[0] else "FrameTime"
    times = sorted(float(row[column]) for row in rows if row.get(column) not in (None, "", "NA"))
    if not times:
        sys.exit("%s: no frame times found" % path)
    slow = times[-max(1, len(times) // 100):]
    return 1000.0 * len(times) / sum(times), 1000.0 * len(slow) / sum(slow), len(times)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    results = []
    for path in sys.argv[1:]:
        average, low, frames = stats(path)
        results.append((average, low))
        print("%-40s avg %7.1f fps   1%% low %7.1f fps   (%d frames)" % (path, average, low, frames))
    if len(results) > 1:
        print("%-40s avg %7.1f fps   1%% low %7.1f fps" % (
            "mean of %d runs" % len(results),
            sum(r[0] for r in results) / len(results), sum(r[1] for r in results) / len(results)))


if __name__ == "__main__":
    main()
