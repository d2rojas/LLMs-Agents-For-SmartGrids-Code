"""Shared chrome for the case-study evaluation pages.

``shell`` holds the stylesheet and the building blocks; ``build`` runs each case
study's generator and assembles the site. Nothing here imports a case study: the
generators run as subprocesses, because the case studies are separate projects
with packages of the same name and dependencies of their own.
"""
