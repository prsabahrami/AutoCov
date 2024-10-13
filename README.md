# AutoCov
Hi!

I decided to make a cli tool designed to help you automatically generate tests for your Python projects until you reach your desired code coverage. Although this project is still in its early stages, my goal is to make achieving your code coverage targets as seamless as possible. The vision for test generation is something like a mixture of Hoare logic along with creating a Digraph out of the uncovered lines and using this to generate tests.

## Features

- [x] **Code Coverage Analysis**: AutoCov analyzes your current code coverage to identify areas that need more tests.
- [ ] **Automated Test Generation**: Using Groq AI, AutoCov generates new tests to improve your coverage.
- [ ] **Iterative Improvement**: The tool runs tests iteratively, enhancing coverage until the specified threshold is met.
- [ ] **Visual Representation**: AutoCov creates a Digraph to visualize your code coverage.
- [ ] **Interactive Test Modification**: It opens an editor window where you can review and modify the generated tests.

## Installation
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
   ```
   python src/main.py
   ```
