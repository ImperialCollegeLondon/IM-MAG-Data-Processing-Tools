"""Main module."""

# import app
import typer

import check_gaps

app = typer.Typer()
app.registered_commands += check_gaps.app.registered_commands #\
#                + other.app.registered_commands

@app.command()
def goodbye(name: str, formal: bool = False):
    if formal:
        print(f"Goodbye Ms. {name}. Have a good day.")
    else:
        print(f"Bye {name}!")


if __name__ == "__main__":
    app()  # pragma: no cover
