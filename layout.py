from rich import print
from rich.layout import Layout

layout = Layout()

layout["lower"].split_row(
    Layout(name="left"),
    Layout(name="right"),
)
print(layout)

print(layout.tree)