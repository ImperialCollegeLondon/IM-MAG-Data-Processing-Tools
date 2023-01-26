import os
from io import TextIOWrapper
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer()

report_file: TextIOWrapper

# use callback because we want this to be the default command
@app.callback(invoke_without_command=True)
def main(data_file: typer.FileText = typer.Argument(...), log_file: Optional[Path] = typer.Option(default='gap-report.txt'), force: bool = typer.Option(False, "--force", "-f")):

    global report_file

    if(log_file.exists()):
        if(force):
            os.remove(log_file)
        else:
            print(f"{log_file} already exists - delete file or use --force")
            raise typer.Abort()

    report_file = open(log_file, "a")

    write_line(f"Checking {data_file.name}")
    for line in data_file:
        print(f"Config line: {line}")

    write_line("Gap report complete")
    report_file.close()


def write_line(message:str):
    print(message)
    report_file.write(message + "\n")


# only needed when this file is run as its own app
if __name__ == "__main__":
    app()
