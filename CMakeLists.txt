cmake_minimum_required (VERSION 3.6)

# Generate config from CubeMX file
execute_process(COMMAND ${CMAKE_SOURCE_DIR}/ioc2cmake.py
    ${CMAKE_SOURCE_DIR}             # Path to source tree
    ${CMAKE_SOURCE_DIR}/TDLAS.ioc   # Path to CubeMX config file
    -s ${CMAKE_SOURCE_DIR}/app      # Extra source folder
    -i ${CMAKE_SOURCE_DIR}/app      # Extra include folder
    -t /opt/gcc-arm-none-eabi-7-2017-q4-major   # Toolchain location
    -v                              # Create vscode properties file
    OUTPUT_VARIABLE ConfigContents)

# Read CUBEMX_* variables from config
foreach(KeyValue ${ConfigContents})
  string(REGEX MATCH "^[^=]+" Key ${KeyValue})
  string(REPLACE "${Key}=" "" Value ${KeyValue})
  set(${Key} "${Value}")
endforeach()

message(STATUS "Project name : ${CUBEMX_PROJNAME}")
message(STATUS "MCU name     : ${CUBEMX_MCUNAME}")

project(${CUBEMX_PROJNAME})

set(OPT "-Og")
set(LIBS "-lc -lm -lnosys -u _printf_float")
set(CMAKE_C_COMPILER "${CUBEMX_TOOLCHAIN}/bin/arm-none-eabi-gcc")

# Set up include directories
string(REPLACE "\n" ";" CUBEMX_INCLUDEDIRS "${CUBEMX_INCLUDEDIRS}")
include_directories("${CUBEMX_INCLUDEDIRS}")

# Check source directories and glob all C files
string(REPLACE "\n" ";" CUBEMX_SOURCEDIRS "${CUBEMX_SOURCEDIRS}")
foreach(SOURCEDIR ${CUBEMX_SOURCEDIRS})
  file(GLOB_RECURSE SOURCEFILES0 ${SOURCEDIR}/*.c)
  list(APPEND SOURCEFILES ${SOURCEFILES0})
endforeach()

# Compiler definitions
add_definitions(${CUBEMX_CDEFS})

# Some trickery to get CMake to deal with our assembler code.
set_property(SOURCE ${CUBEMX_STARTUPFILE} PROPERTY LANGUAGE C)

# Burn git commit hash to firmware file
add_custom_command(
    OUTPUT  version.c _ # "_" is dummy output, so this command runs on every build
    COMMAND ${CMAKE_COMMAND}
        -D INPUT_FILE=${CMAKE_CURRENT_SOURCE_DIR}/app/version.c.in
        -D OUTPUT_FILE=${CMAKE_CURRENT_BINARY_DIR}/version.c
        -P ${CMAKE_CURRENT_SOURCE_DIR}/gen_version.cmake
)

# Compile all sources to .elf file
add_executable(
    ${CUBEMX_PROJNAME}.elf
    ${SOURCEFILES}
    ${CUBEMX_STARTUPFILE}
    ${CMAKE_CURRENT_BINARY_DIR}/version.c
)
target_link_libraries(${CUBEMX_PROJNAME}.elf ${LIBS})

# Set compiler flags
set_target_properties(
    ${CUBEMX_PROJNAME}.elf PROPERTIES COMPILE_FLAGS
    "${CUBEMX_MCUFLAGS} ${OPT} -Wall -fdata-sections -ffunction-sections "
)

# Set linker flags
set_target_properties(
    ${CUBEMX_PROJNAME}.elf PROPERTIES LINK_FLAGS
    "${CUBEMX_MCUFLAGS} -specs=nano.specs -T${CMAKE_SOURCE_DIR}/${CUBEMX_LDFILE} \
    -Wl,-Map=${PROJECT_BINARY_DIR}/${CUBEMX_PROJNAME}.map,--cref -Wl,--gc-sections")

# Convert .elf to .bin
add_custom_target(${CUBEMX_PROJNAME}.bin ALL
    "${CUBEMX_TOOLCHAIN}/bin/arm-none-eabi-objcopy" -Obinary
    "${PROJECT_BINARY_DIR}/${CUBEMX_PROJNAME}.elf"
    "${PROJECT_BINARY_DIR}/${CUBEMX_PROJNAME}.bin"
    DEPENDS ${CUBEMX_PROJNAME}.elf
    COMMENT "Generating .bin file"
)

# Convert .elf to .hex
add_custom_target(${CUBEMX_PROJNAME}.hex ALL
    "${CUBEMX_TOOLCHAIN}/bin/arm-none-eabi-objcopy" -Oihex
    "${PROJECT_BINARY_DIR}/${CUBEMX_PROJNAME}.elf"
    "${PROJECT_BINARY_DIR}/${CUBEMX_PROJNAME}.hex"
    DEPENDS ${CUBEMX_PROJNAME}.elf
    COMMENT "Generating .hex file"
)

# Flash firmware to target
add_custom_target(flash
    st-flash --format ihex write ${CUBEMX_PROJNAME}.hex
    DEPENDS ${CUBEMX_PROJNAME}.hex
    COMMENT "Flashing target hardware")

# Copy firmware to installation medium
#install(FILES ${PROJECT_BINARY_DIR}/${CUBEMX_PROJNAME}.bin
#    DESTINATION /foo/bar
#    PERMISSIONS OWNER_WRITE OWNER_READ GROUP_READ WORLD_READ
#)
