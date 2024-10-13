import argparse
from coverage import Coverage
from groq import Groq
import os
import pytest
from dotenv import load_dotenv
import logging
import requests
from typing import List
from functools import wraps
import sys
import rich
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

console = Console()

# Add this function to create a styled header
def print_header():
    console.print(Panel.fit(
        "[bold cyan]AutoCov[/bold cyan]: Automatically create tests and check code coverage",
        border_style="bold magenta"
    ))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_with_error_handling(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ModuleNotFoundError, ImportError) as e:
            module_name = str(e).split("'")[1]
            console.print(f"[bold yellow]Module not found: {module_name}. Attempting to install...[/bold yellow]")
            install_missing_module(module_name)
            # Try to run the function again after installing the module
            return func(*args, **kwargs)
    return wrapper

@run_with_error_handling
def run_tests(project_path):
    console.print("[bold green]Running tests...[/bold green]")
    tests_dir = os.path.join(project_path, "tests")
    return pytest.main(['-v', tests_dir])

def analyze_coverage(project_path):
    console.print("[bold green]Analyzing coverage...[/bold green]")
    src_dir = os.path.join(project_path, "src")
    if not os.path.exists(src_dir):
        # If 'src' doesn't exist, use the project name as the source directory
        project_name = os.path.basename(project_path)
        src_dir = os.path.join(project_path, project_name)
    
    if not os.path.exists(src_dir):
        console.print(f"[bold red]Source directory not found in {project_path}[/bold red]")
        return 0

    cov = Coverage(source=[src_dir], omit=["*/tests/*"]) # TODO: Add branch coverage
    cov.start()

    run_tests(project_path)

    cov.stop()
    cov.save()
    
    cov.load()
    coverage_percentage = cov.report()
    return coverage_percentage

def get_source_files(project_path):
    src_dir = os.path.join(project_path, "src")
    if not os.path.exists(src_dir):
        # If 'src' doesn't exist, use the project name as the source directory
        project_name = os.path.basename(project_path)
        src_dir = os.path.join(project_path, project_name)
    
    if not os.path.exists(src_dir):
        console.print(f"[bold red]Source directory not found in {project_path}[/bold red]")
        return []
    source_files = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                source_files.append(os.path.join(root, file))
    return source_files

def get_existing_tests(project_path):
    tests_dir = os.path.join(project_path, "tests")
    existing_tests = []
    for root, _, files in os.walk(tests_dir):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                with open(os.path.join(root, file), 'r') as f:
                    existing_tests.append(f.read())
    return "\n\n".join(existing_tests)

def analyze_uncovered_parts(file, project_path):
    cov = Coverage()
    cov.load()
    
    with open(file, 'r') as f:
        lines = f.readlines()
    
    uncovered_lines = cov.analysis(file)[2]
    uncovered_functions = []
    current_function = None
    
    for i, line in enumerate(lines, 1):
        if line.strip().startswith('def '):
            current_function = line.strip().split('def ')[1].split('(')[0]
        if i in uncovered_lines and current_function:
            uncovered_functions.append(current_function)
    
    uncovered_functions = list(set(uncovered_functions))
    
    return f"Focus on these uncovered functions: {', '.join(uncovered_functions)}. " \
           f"Pay special attention to edge cases and boundary conditions."

def get_project_context(project_path):
    source_files = get_source_files(project_path)
    
    context = f"Project root: {project_path}\n"
    context += f"Source files:\n"
    
    for file in source_files:
        relative_path = os.path.relpath(file, project_path)
        with open(file, 'r') as f:
            lines = f.readlines()
        functions = [line.strip().split('def ')[1].split('(')[0] 
                     for line in lines if line.strip().startswith('def ')]
        context += f"- {relative_path}:\n"
        context += f"  Functions: {', '.join(functions)}\n"
    
    return context

def get_test_examples():
    return """
    Example 1:
    def test_addition():
        assert add(2, 3) == 5
        assert add(-1, 1) == 0
        assert add(0, 0) == 0

    Example 2:
    @pytest.mark.parametrize("input,expected", [
        ("hello", "HELLO"),
        ("world", "WORLD"),
        ("", ""),
    ])
    def test_uppercase(input, expected):
        assert uppercase(input) == expected
    """

def post_process_tests(generated_tests):
    lines = generated_tests.split('\n')
    processed_lines = []
    
    for line in lines:
        # Ensure proper indentation
        line = line.strip()
        if line.startswith('def test_'):
            processed_lines.append('\n' + line)
        else:
            processed_lines.append('    ' + line)
        
        # Add assertions if missing
        if 'assert' not in line and line.strip() != '':
            processed_lines.append('    assert False, "Add an assertion here"')
    
    # Add import statement if missing
    if 'import pytest' not in generated_tests:
        processed_lines.insert(0, 'import pytest\n')
    
    return '\n'.join(processed_lines)

def generate_tests(project_path, groq_client, model):
    source_files = get_source_files(project_path)
    existing_tests = get_existing_tests(project_path)
    
    for file in source_files:
        console.print(f"[bold green]Generating tests for {file}[/bold green]")
        with open(file, 'r') as f:
            code = f.read()
        
        uncovered_parts = analyze_uncovered_parts(file, project_path)
        
        context = get_project_context(project_path)
        examples = get_test_examples()
        
        prompt = f"""
        Generate pytest tests for the following Python code:

        {code}

        Project context:
        {context}

        Existing tests:
        {existing_tests}

        Focus on these uncovered parts and edge cases:
        {uncovered_parts}

        Use these examples as a guide for writing good tests:
        {examples}

        Generate comprehensive tests that cover various scenarios and edge cases.
        """
        
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
            )
            
            generated_tests = response.choices[0].message.content
            
            processed_tests = post_process_tests(generated_tests)
            
            test_file = f"tests/test_{os.path.basename(file)}"
            with open(test_file, 'a') as f:
                f.write(processed_tests)
            console.print(f"[bold green]Tests written to {test_file}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Error generating tests for {file}: {str(e)}[/bold red]")

def install_dependencies(project_path):
    console.print("[bold green]Installing project dependencies...[/bold green]")
    requirements_file = os.path.join(project_path, "requirements.txt")
    pyproject_file = os.path.join(project_path, "pyproject.toml")
    
    if os.path.exists(requirements_file):
        os.system(f"pip install -r {requirements_file}")
    elif os.path.exists(pyproject_file):
        os.system(f"pip install {project_path}")
    else:
        console.print("[bold yellow]No requirements.txt or pyproject.toml found. Skipping dependency installation.[/bold yellow]")

def install_missing_module(module_name):
    console.print(f"[bold green]Installing missing module: {module_name}[/bold green]")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", module_name])
        console.print(f"[bold green]Successfully installed {module_name}[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Failed to install {module_name}. Error: {e}[/bold red]")
        raise

def get_available_models(api_key: str) -> List[str]:
    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return [model['id'] for model in response.json()['data']]
    else:
        console.print(f"[bold red]Failed to fetch models: {response.status_code}[/bold red]")
        return []

DEFAULT_MODEL = "llama3-groq-70b-8192-tool-use-preview"

# Update the main function
def main():
    load_dotenv()
    print_header()

    project_path = console.input("[bold]Enter the path to the project folder: [/bold]").strip()
    coverage_limit = float(console.input("[bold]Enter the coverage limit in percentage: [/bold]").strip())
    model = console.input(f"[bold]Enter the model to use for generating tests (default: {DEFAULT_MODEL}): [/bold]").strip() or DEFAULT_MODEL

    project_path = os.path.abspath(project_path)

    with console.status("[bold green]Installing project dependencies...", spinner="dots"):
        install_dependencies(project_path)

    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        console.print("[bold red]GROQ_API_KEY not found in environment variables[/bold red]")
        return

    with console.status("[bold green]Fetching available models...", spinner="dots"):
        available_models = get_available_models(groq_api_key)
    
    if not available_models:
        console.print("[bold red]Failed to fetch available models[/bold red]")
        return

    if model not in available_models:
        console.print(f"[bold yellow]Specified model '{model}' is not available. Using default model '{DEFAULT_MODEL}'[/bold yellow]")
        model = DEFAULT_MODEL
    else:
        model = model

    groq_client = Groq(api_key=groq_api_key)

    current_coverage = 0
    iteration = 0
    max_iterations = 5  # Prevent infinite loops

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Generating tests...", total=max_iterations)

        while current_coverage < coverage_limit and iteration < max_iterations:
            iteration += 1
            progress.update(task, advance=1, description=f"[cyan]Iteration {iteration}")
            
            try:
                console.print(f"\n[bold blue]Starting iteration {iteration}[/bold blue]")
                current_coverage = analyze_coverage(project_path)
                console.print(f"[bold green]Current coverage: {current_coverage}%[/bold green]")

                if current_coverage < coverage_limit:
                    console.print(f"[bold yellow]Coverage is below the target of {coverage_limit}%[/bold yellow]")
                    user_input = console.input(f"[bold]Do you want to proceed with generating tests for iteration {iteration}? (y/n): [/bold]")
                    console.print(f"[italic]User input received: {user_input}[/italic]")
                    
                    if user_input.lower() != 'y':
                        console.print("[yellow]Test generation stopped by user.[/yellow]")
                        break
                    
                    console.print(f"[bold blue]Generating tests for iteration {iteration}...[/bold blue]")
                    generate_tests(project_path, groq_client, model)
                    
                    console.print(f"[bold green]Tests generated for iteration {iteration}.[/bold green]")
                    user_input = console.input("[bold]Do you want to review the generated tests before running them? (y/n): [/bold]")
                    console.print(f"[italic]User input received: {user_input}[/italic]")
                    
                    if user_input.lower() == 'y':
                        console.print("[yellow]Please review the generated tests in the 'tests' directory.[/yellow]")
                        console.input("[bold]Press Enter when you're ready to continue...[/bold]")
                    
                    console.print(f"[bold blue]Running tests for iteration {iteration}...[/bold blue]")
                    run_tests(project_path)
                else:
                    console.print(f"[bold green]Target coverage of {coverage_limit}% reached![/bold green]")
                    break
            except Exception as e:
                console.print(f"[bold red]Error in iteration {iteration}: {str(e)}[/bold red]")
                break

            console.print(f"[bold cyan]End of iteration {iteration}[/bold cyan]\n")

        console.print(f"[bold yellow]Maximum iterations reached. Final coverage: {current_coverage}%[/bold yellow]")
    if iteration == max_iterations:
        console.print(f"\n[bold cyan]Final coverage: {current_coverage}%[/bold cyan]")
    if current_coverage >= coverage_limit:
        console.print("[bold green]Target coverage reached successfully![/bold green]")
    else:
        console.print(f"[bold yellow]Target coverage of {coverage_limit}% not reached. Consider running the tool again or adjusting your tests manually.[/bold yellow]")

if __name__ == "__main__":
    main()
