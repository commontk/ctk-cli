from setuptools import setup, find_packages

setup(
    name = "ctk-cli",
    version = "1.4",
    packages = find_packages(),
    description = "Python interface for inspecting and running CLI modules (as defined by CommonTK)",
    license = 'Apache 2.0',
    keywords = "CTK CLI Slicer host plugin module execution model XML",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2'
    ],
    author='Hans Meine',
    author_email='hans_meine@gmx.net',
    url='https://github.com/commontk/ctk-cli'
)
