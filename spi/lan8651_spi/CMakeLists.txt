add_executable(lan8651_spi
        lan8651_spi.c
        )

# pull in common dependencies and additional spi hardware support
target_link_libraries(lan8651_spi pico_stdlib hardware_spi)

# create map/bin/hex file etc.
pico_add_extra_outputs(lan8651_spi)

# add url via pico_set_program_url
example_auto_set_url(lan8651_spi)

pico_enable_stdio_usb(lan8651_spi 1)
pico_enable_stdio_uart(lan8651_spi 0)