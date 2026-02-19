# Contributing to Crest (Custom REST Command)

First off, thank you for considering contributing to Crest! This command is designed to make HTTP requests from Splunk as flexible and powerful as possible. Community contributions help keep it that way.

The following is a set of guidelines for contributing to Crest hosted on GitHub. 

## 1. Getting Started

We use the standard GitHub "Fork and Pull Request" workflow. 

1. **Fork** the repository to your own GitHub account.
2. **Clone** the project to your local machine.
3. **Create a branch** for your feature or bug fix (e.g., `git checkout -b feature/add-new-auth-type`).

## 2. Setting Up Your Splunk Environment

To develop and test your changes, you need a local Splunk Enterprise instance.

1. Copy or symlink your cloned repository into your local Splunk apps directory:
   `$SPLUNK_HOME/etc/apps/crest`
2. Restart Splunk to ensure all configuration files (`commands.conf`, `app.conf`) and Python scripts are loaded.
3. Make your code changes in your local repository.

## 3. Testing Your Changes

Because `crest` interacts with external systems, testing is crucial. Please ensure your changes do not break existing functionality for Generating or Streaming modes.

* **Use Debug Mode:** When building new payload formatting or header parsing, use the built-in `debug=true` parameter. This ensures you are verifying the exact output of your code without accidentally spamming external APIs.
  `| crest url="https://httpbin.org/post" method="post" debug=true`
* **Test Both Modes:** If you modify core logic, test the command as the first command in a search (Generating) and piped after `makeresults` (Streaming).
* **Test Token Substitution:** If modifying streaming behavior, ensure token substitution (`$field$`) still evaluates correctly.
* **Check Splunk Logs:** Review `search.log` and Splunk internal logs (`index=_internal`) for any Python tracebacks or command errors during execution.

## 4. Submitting a Pull Request

Once your code is ready and tested, push your branch to your GitHub fork and open a Pull Request (PR) against the main repository.

In your PR description, please include:
* A clear title and description of the problem you are solving or the feature you are adding.
* The exact SPL query you used to test the changes.
* Example output or screenshots (if applicable).
* Confirmation that you have tested the changes locally in Splunk.

## Code of Conduct

* Keep the code clean, well-commented, and aligned with standard Splunk Python SDK practices.
* Be respectful and constructive in PR discussions.

Thank you for helping improve Crest!
