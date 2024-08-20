from setuptools import setup, find_packages

setup(
    name='treasure_hunt',
    version='1.0',
    description='A treasure hunt game built with pygame',
    author='Kaleb Bishop',
    author_email='kaleb.bishop@colorado.edu',
    url='https://github.com/kalebishop',
    package_data={
        'treasure_hunt': ['assets/*', 'maps/*', 'saves/', 'telemetry/']
    },
    packages=find_packages(),
    install_requires=['pygame'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
    ],
)