# AutoCov

AutoCov is a CLI tool that automatically creates tests for your Python project until it reaches a specified code coverage threshold.

## Features

- Analyzes current code coverage
- Generates new tests using Groq AI
- Iteratively improves coverage until the target is reached

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/prsabahrami/autocov.git
   cd autocov
   ```

2. Install the package:
   ```
   pip install -e .
   ```

3. Set up your Groq API key:
   Create a `.env` file in the project root and add your Groq API key:
   ```
   GROQ_API_KEY=your_api_key_here
   ```

## Usage

Run AutoCov with the following command:
