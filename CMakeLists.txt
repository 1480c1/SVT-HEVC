cmake_minimum_required(VERSION 2.8.12)

if("${CMAKE_CURRENT_SOURCE_DIR}" STREQUAL "${CMAKE_CURRENT_BINARY_DIR}")
    message(WARNING "Building in-source is highly not recommended\n"
                    "Please use the Build folder or create your own.")
endif()

if(NOT CMAKE_BUILD_TYPE AND NOT (MSVC OR CMAKE_GENERATOR STREQUAL "Xcode"))
    set(CMAKE_BUILD_TYPE Release)
endif()

option(YASM "Use yasm (if present in PATH)" ON)
if(YASM)
    find_program(YASM_EXE yasm)
    if(YASM_EXE AND NOT CMAKE_ASM_NASM_COMPILER MATCHES "yasm")
        set(CMAKE_ASM_NASM_COMPILER ${YASM_EXE})
    endif()
endif()

project(svt-hevc)

set(SVT_HEVC_VERSION_MAJOR           "1")
set(SVT_HEVC_VERSION_MINOR           "4")
set(SVT_HEVC_VERSION_PATCHLEVEL      "2")
set(SVT_HEVC_VERSION "${SVT_HEVC_VERSION_MAJOR}.${SVT_HEVC_VERSION_MINOR}.${SVT_HEVC_VERSION_PATCHLEVEL}")

# BUILD_SHARED_LIBS is a standard CMake variable, but we declare it here to
# make it prominent in the GUI.
option(BUILD_SHARED_LIBS "Build shared libraries (DLLs)." ON)
option(COVERAGE "Generate coverage report")
option(BUILD_APP "Build Enc App" ON)
option(COMPILE_AS_CPP "Compile C Source files with a c++ compiler")
if(NOT MSVC)
    option(NATIVE "Build for native performance (march=native)")
endif()

if(COMPILE_AS_CPP)
    enable_language(CXX)
    include(CheckCXXCompilerFlag)
else()
    enable_language(C)
    include(CheckCCompilerFlag)
endif()

enable_language(ASM_NASM)

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(WARNING "32-bit is not supported")
endif()

include(GNUInstallDirs)

message(STATUS "CMAKE_BUILD_TYPE = ${CMAKE_BUILD_TYPE}")
message(STATUS "CMAKE_C_COMPILER = ${CMAKE_C_COMPILER}")
if(COMPILE_AS_CPP)
    message(STATUS "CMAKE_CXX_COMPILER = ${CMAKE_CXX_COMPILER}")
endif()
message(STATUS "CMAKE_ASM_NASM_COMPILER = ${CMAKE_ASM_NASM_COMPILER}")
if(CMAKE_AR)
    message(STATUS "CMAKE_AR = ${CMAKE_AR}")
endif()
if(CMAKE_RANLIB)
    message(STATUS "CMAKE_RANLIB = ${CMAKE_RANLIB}")
endif()
message(STATUS "CMAKE_INSTALL_PREFIX = ${CMAKE_INSTALL_PREFIX}")


configure_file(${PROJECT_SOURCE_DIR}/Source/API/EbApiVersion.h.in ${PROJECT_SOURCE_DIR}/Source/API/EbApiVersion.h @ONLY)

set(SVT_HEVC_SOVERSION 1)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Bin/${CMAKE_BUILD_TYPE}/)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Bin/${CMAKE_BUILD_TYPE}/)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Bin/${CMAKE_BUILD_TYPE}/)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)
if(CMAKE_VERSION VERSION_LESS "3.1")
    if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
        set(CMAKE_C_FLAGS "--std=gnu99 ${CMAKE_C_FLAGS}")
    endif()
else()
    set(CMAKE_C_STANDARD 99)
endif()
set(CAN_USE_ASSEMBLER TRUE)
set(CMAKE_INCLUDE_CURRENT_DIR ON)

if(UNIX)
    if(APPLE)
        set(CMAKE_MACOSX_RPATH 1)
        set(CMAKE_C_ARCHIVE_CREATE   "<CMAKE_AR> Scr <TARGET> <LINK_FLAGS> <OBJECTS>")
        set(CMAKE_CXX_ARCHIVE_CREATE "<CMAKE_AR> Scr <TARGET> <LINK_FLAGS> <OBJECTS>")
        set(CMAKE_C_ARCHIVE_FINISH   "<CMAKE_RANLIB> -no_warning_for_no_symbols -c <TARGET>")
        set(CMAKE_CXX_ARCHIVE_FINISH "<CMAKE_RANLIB> -no_warning_for_no_symbols -c <TARGET>")
    else()
        set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -z noexecstack -z relro -z now -pie ")
    endif()
endif()

set(flags_to_test
    -Wextra
    -Wformat
    -Wformat-security
    -fPIE
    -fPIC
    -D_FORTIFY_SOURCE=2
    /GS
    /sdl)
if(MSVC)
    list(APPEND flags_to_test /MP)
else()
    list(INSERT flags_to_test 0 -Wall)
    #for Mingw64 support, see https://gcc.gnu.org/bugzilla/show_bug.cgi?id=65782
    if(MINGW)
        list(APPEND flags_to_test -fno-asynchronous-unwind-tables -mxsave)
    else()
        list(APPEND flags_to_test -fstack-protector-strong)
    endif()
    if(NATIVE)
        list(APPEND flags_to_test -march=native)
    endif()
endif()
set(release_flags_to_test
    -O2
    -O3)
set(debug_flags_to_test
    -O0)

if(MSVC)
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} /NXCompat /DynamicBase")
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} /NXCompat /DynamicBase")
endif()

foreach(flag ${flags_to_test};${release_flags_to_test};${debug_flags_to_test})
    string(REGEX REPLACE "[^A-Za-z0-9]" "_" flag_var "${flag}")
    set(test_c_flag "C_FLAG${flag_var}")
    if(COMPILE_AS_CPP)
        set(test_cxx_flag "CXX_FLAG${flag_var}")
    endif()
    check_c_compiler_flag(${flag} "${test_c_flag}")
    if(COMPILE_AS_CPP)
        check_cxx_compiler_flag(${flag} "${test_cxx_flag}")
    endif()
    list(FIND release_flags_to_test ${flag} r_flag)
    list(FIND debug_flags_to_test ${flag} d_flag)
    if(${test_c_flag})
        if(NOT r_flag EQUAL -1)
            set(CMAKE_C_FLAGS_RELEASE "${CMAKE_C_FLAGS_RELEASE} ${flag}")
        elseif(NOT d_flag EQUAL -1)
            set(CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} ${flag}")
        else()
            set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${flag}")
        endif()
    endif()
    if(COMPILE_AS_CPP)
        if(${test_cxx_flag})
            if(NOT r_flag EQUAL -1)
                set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} ${flag}")
            elseif(NOT d_flag EQUAL -1)
                set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} ${flag}")
            else()
                set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${flag}")
            endif()
        endif()
    endif()
endforeach()

if(CMAKE_ASM_NASM_OBJECT_FORMAT MATCHES "win")
    set(CMAKE_ASM_NASM_FLAGS_DEBUG "${CMAKE_ASM_NASM_FLAGS_DEBUG} -gcv8")
elseif(CMAKE_ASM_NASM_OBJECT_FORMAT MATCHES "macho")
    if(CMAKE_ASM_NASM_COMPILER MATCHES "nasm")
        set(CMAKE_ASM_NASM_FLAGS_DEBUG "${CMAKE_ASM_NASM_FLAGS_DEBUG} -gdwarf")
    elseif(CMAKE_ASM_NASM_COMPILER MATCHES "yasm")
        set(CMAKE_ASM_NASM_FLAGS_DEBUG "${CMAKE_ASM_NASM_FLAGS_DEBUG} -gnull")
    endif()
else()
    if(CMAKE_ASM_NASM_COMPILER MATCHES "nasm")
        set(CMAKE_ASM_NASM_FLAGS_DEBUG "${CMAKE_ASM_NASM_FLAGS_DEBUG} -gdwarf")
    elseif(CMAKE_ASM_NASM_COMPILER MATCHES "yasm")
        set(CMAKE_ASM_NASM_FLAGS_DEBUG "${CMAKE_ASM_NASM_FLAGS_DEBUG} -gdwarf2")
    endif()
endif()

# Prepare for Coveralls
if(COVERAGE AND NOT MSVC)
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} --coverage")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --coverage")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} --coverage")
endif()

# Add Subdirectories
add_subdirectory(Source/Lib)
if(BUILD_APP)
    add_subdirectory(Source/App)
endif()

install(DIRECTORY ${PROJECT_SOURCE_DIR}/Source/API/ DESTINATION "${CMAKE_INSTALL_FULL_INCLUDEDIR}/svt-hevc" FILES_MATCHING PATTERN "*.h")
