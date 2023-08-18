---
layout: default
title: Setup and testing
parent: Contributing
nav_order: 0
---

# Setup and testing

## Installation

To install requires development tools:

```bash
pip install aws-orga-deployer[dev]
```

The source code is available in [GitHub](https://github.com/malaval/aws-orga-deployer). A `Makefile` is available at the root folder with basic commands.

## Testing

Testing does not require an AWS account or credentials. We use [moto](https://github.com/getmoto/moto) to mock AWS services.

To run all unit tests, you can execute `make test`.
