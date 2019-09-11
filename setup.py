from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='sleprovider',
    version='0.0.1',
    author='VisionSpace Technologies GmbH',
    author_email="oss@visionspace.com",
    description='Python Space Link Extension Provider',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="www.visionspace.com",
    license='AGPL-3.0',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Framework :: Twisted"
    ],
    python_requires='>=3',
    keywords='sle provider',
    packages=find_packages(exclude=['build', '*.build', 'build.*', '*.build.*',
                                    'dist', '*.dist', 'dist.*', '*.dist.*',
                                    'examples', '*.examples', 'examples.*', '*.examples.*',
                                    'tests', '*.tests', 'tests.*', '*.tests.*']),
    install_requires=['pyasn1==0.4.5', 'bitstring', 'twisted', 'klein', 'werkzeug',
                      'PyOpenSSL', 'service_identity', 'slecommon'],
    extra_require={'Coretex': ['caretex']}
)
