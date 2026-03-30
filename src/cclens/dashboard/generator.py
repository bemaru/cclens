from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def generate_dashboard(data: dict, output_path: str | None = None) -> str:
    """Generate HTML dashboard and return the output path."""
    if output_path is None:
        output_path = str(Path.home() / ".claude" / "cclens-dashboard.html")

    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)
    template = env.get_template("dashboard.html")

    html = template.render(data=data)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
