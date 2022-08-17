# Make sure to update package.json, too!
version_info = (5, 5, 0, "b1")

if len(version_info) <= 3:
    version_extra = ""
else:
    version_extra = version_info[3]  # type: ignore

__version__ = ".".join(map(str, version_info[:3])) + version_extra
