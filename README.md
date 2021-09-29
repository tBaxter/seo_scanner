## A simple SEO scanner based on the 18F Domain Scan project.

### Requirements and installation

`domain-scan` requires **Python 3.6 or 3.7** and **pipenv**

If you're not sure that you have pipenv installed already, run 
`pip install pipenv`

Once you're sure it's installed, then install the dependencies:
`pipenv install`

And then open a shell in your pipenv environment:
`pipenv shell`

You can now safely run the scanner locally.

### Usage

### Scanning a single domain

To scan a single domain, in this case, whitehouse.gov, you'd run:

```bash
python seo.py whitehouse.gov
```

Note that your domain should be the domain only, without any `https://` or trailing `/`

### Scanning multiple domains

To scan multiple domains, pass them as a comma-separated list, with no spaces:

```bash
python seo.py whitehouse.gov,gsa.gov
```

The output will be written to `scan_output.csv`

### Public domain

This project is in the worldwide [public domain](LICENSE.md). As stated in [CONTRIBUTING](CONTRIBUTING.md):

> This project is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/).
>
> All contributions to this project will be released under the CC0 dedication. By submitting a pull request, you are agreeing to comply with this waiver of copyright interest.
