;;   guix shell             # drop into dev shell with tools & libs
;;   guix build -f guix.scm # build an installable package
;;   guix shell -D -f guix.scm

(define-module (smk)
  #:use-module (guix)	     
  #:use-module (guix gexp)
  #:use-module (guix packages)
  #:use-module (guix git-download)
  #:use-module (guix build-system pyproject)
  #:use-module (guix licenses)
  #:use-module (gnu packages)
  #:use-module (alex packages basedpyright))


(define vcs-file?
  ;; Return true if the given file is under version control.
  (or (git-predicate (dirname (dirname (current-source-directory))))
      (const #t)))


(define-public smk
 (package
 (name "smk")
 (version "0.1.0")
 (source (local-file "../.." "smk-checkout"
                      #:recursive? #t
                      #:select? vcs-file?)) ; TODO update to git -> to pypi when uploaded
 (build-system pyproject-build-system)
 (arguments
  `(#:tests? #f))
 (propagated-inputs
  (specifications->packages '("python-typer" "python-rich")))
 (native-inputs (specifications->packages '("python-setuptools" "node-basedpyright")))
 (synopsis "Tiny buid script for C/C++ written in Python")
 (description "Smk is a dead simple build script for C/C++. It supports singe-executable builds only. Incremental and parallel builds are supported. Can detect system libraries as dependencies.")
 (home-page "https://github.com/alex-iam/smk")
 (license gpl3+)))
smk
