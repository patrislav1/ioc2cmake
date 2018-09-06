execute_process(COMMAND git --no-pager describe --dirty --always --tags --abbrev=4 OUTPUT_VARIABLE GITVERSION OUTPUT_STRIP_TRAILING_WHITESPACE)
execute_process(COMMAND date "+%F %T" OUTPUT_VARIABLE BUILDDATE OUTPUT_STRIP_TRAILING_WHITESPACE)
configure_file(${INPUT_FILE} ${OUTPUT_FILE})
message("git version info: ${GITVERSION}")
