import csv
import os
from io import TextIOWrapper
from pathlib import Path
from typing import Optional

import typer

from science_mode import *

app = typer.Typer()

report_file: TextIOWrapper

# use callback because we want this to be the default command
@app.callback(invoke_without_command=True)
def main(data_file: typer.FileText = typer.Argument(...), \
         report_file_path: Optional[Path] = typer.Option('gap-report.txt',"--report"), \
         mode:Mode = typer.Option(Mode.unknown,"--mode", "-m", case_sensitive=False)  ,\
         force: bool = typer.Option(False, "--force", "-f")):

    global report_file

    mode = validate_check_gap_args(data_file, report_file_path, mode, force)

    report_file = open(report_file_path, "a")
    mode_config = ModeConfig(mode)

    write_line(f"Checking {data_file.name}")

    line_count = 0
    #reader = csv.reader(data_file, delimiter=',', quotechar='|')
    #with open(data_file, mode='r') as csv_file:
    reader = csv.DictReader(data_file)
    for row in reader:
        sequence = row['sequence']
        pri_coarse = row['pri_coarse']
        pri_fine = row['pri_fine']
        sec_coarse = row['sec_coarse']
        sec_fine = row['sec_fine']

        print(f"Seq: {row['sequence']}")

        line_count += 1

    write_line("Gap report complete")
    report_file.close()

def validate_check_gap_args(data_file, report_file_path, mode, force):
    if(report_file_path.exists()):
        if(force):
            os.remove(report_file_path)
        else:
            print(f"{report_file_path} already exists - delete file or use --force")
            raise typer.Abort()

    if("burst" in data_file.name and mode == Mode.unknown):
        mode = Mode.burst128
    elif("normal" in data_file.name and mode == Mode.unknown):
        mode = Mode.normal

    if(mode == Mode.unknown):
        print(f"unable to determine the mode - specify --mode NormalE8, --mode BurstE64. See --help for more info.")
        raise typer.Abort()
    return mode


def write_line(message:str):
    print(message)
    report_file.write(message + "\n")


# only needed when this file is run as its own app
if __name__ == "__main__":
    app()
