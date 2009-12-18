<?xml version="1.0" encoding="UTF-8"?>
<structure version="9" htmlmode="strict" relativeto="*SPS" encodinghtml="UTF-8" encodingrtf="ISO-8859-1" encodingpdf="UTF-8" useimportschema="1" embed-images="1">
	<parameters/>
	<schemasources>
		<namespaces>
			<nspair prefix="sb" uri="skylinebill"/>
			<nspair prefix="ub" uri="utilitybill"/>
		</namespaces>
		<schemasources>
			<xsdschemasource name="XML" main="1" schemafile="C:\workspace-skyline\billing\UtilityBill.xsd" workingxmlfile="C:\workspace-skyline\billing\bills\Skyline-1-1.xml">
				<xmltablesupport/>
				<textstateicons/>
			</xsdschemasource>
		</schemasources>
	</schemasources>
	<modules>
		<module spsfile="BillPresentment.sps"/>
	</modules>
	<flags>
		<scripts/>
		<globalparts/>
		<designfragments/>
		<pagelayouts/>
	</flags>
	<scripts>
		<script language="javascript"/>
	</scripts>
	<importedxslt/>
	<globalstyles/>
	<mainparts>
		<children>
			<globaltemplate subtype="main" match="/">
				<children>
					<documentsection>
						<properties columncount="1" columngap="0.50in" headerfooterheight="fixed" pagemultiplepages="0" pagenumberingformat="1" pagenumberingstartat="auto" pagestart="next" paperheight="11in" papermarginbottom="0.79in" papermarginfooter="0.30in" papermarginheader="0.30in" papermarginleft="0.60in" papermarginright="0.60in" papermargintop="0.79in" paperwidth="8.50in"/>
					</documentsection>
					<tgrid>
						<properties border="0" cellpadding="0" cellspacing="0" width="100%"/>
						<styles border-collapse="collapse"/>
						<children>
							<tgridbody-cols>
								<children>
									<tgridcol>
										<properties width="61px"/>
										<styles width="61px"/>
									</tgridcol>
									<tgridcol>
										<styles width="76px"/>
									</tgridcol>
									<tgridcol/>
									<tgridcol>
										<styles width="61px"/>
									</tgridcol>
								</children>
							</tgridbody-cols>
							<tgridbody-rows>
								<children>
									<tgridrow>
										<styles height="87px"/>
										<children>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/logo-tl.png)"/>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/logo-tr.png)" background-repeat="no-repeat"/>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/t.png)"/>
												<children>
													<image>
														<target>
															<fixtext value="images\EmeraldCity-1024\skyline.png"/>
														</target>
														<imagesource>
															<fixtext value="images\EmeraldCity-1024\skyline.png"/>
														</imagesource>
													</image>
												</children>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/tr.png)"/>
											</tgridcell>
										</children>
									</tgridrow>
									<tgridrow>
										<styles height="211px"/>
										<children>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/logo-bl.png)" background-repeat="no-repeat"/>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/logo-br.png)" background-repeat="no-repeat"/>
											</tgridcell>
											<tgridcell>
												<children>
													<tgrid>
														<properties align="center" border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties align="center"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h1">
																						<children>
																							<text fixtext="Guaranteed Savings through Green Energy">
																								<styles color="#0c743c" font-family="Arial" font-style="normal" font-weight="normal"/>
																							</text>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
													<tgrid>
														<properties border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="50%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties width="50%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Account Number"/>
																						</children>
																					</paragraph>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties width="5%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="95%"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell/>
																											<tgridcell>
																												<children>
																													<template subtype="source" match="XML">
																														<children>
																															<template subtype="element" match="ub:utilitybill">
																																<children>
																																	<template subtype="attribute" match="account">
																																		<children>
																																			<content/>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Utility Account Number"/>
																						</children>
																					</paragraph>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties width="5%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="95%"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell/>
																											<tgridcell>
																												<children>
																													<template subtype="source" match="XML">
																														<children>
																															<template subtype="element" match="ub:utilitybill">
																																<children>
																																	<template subtype="element" match="ub:car">
																																		<children>
																																			<template subtype="element" match="ub:accountnumber">
																																				<children>
																																					<content/>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
													<newline/>
													<tgrid>
														<properties border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="50%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties width="50%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Billing Address"/>
																						</children>
																					</paragraph>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties width="5%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="95%"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell/>
																											<tgridcell>
																												<children>
																													<tgrid>
																														<properties border="0"/>
																														<children>
																															<tgridbody-cols>
																																<children>
																																	<template subtype="source" match="XML">
																																		<children>
																																			<template subtype="element" match="ub:utilitybill">
																																				<children>
																																					<template subtype="element" match="ub:car">
																																						<children>
																																							<template subtype="element" match="ub:billingaddress">
																																								<children>
																																									<tgridcol/>
																																								</children>
																																								<variables/>
																																							</template>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																															</tgridbody-cols>
																															<tgridbody-rows>
																																<children>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:addressee">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:street">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:city">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																					<text fixtext=", "/>
																																					<template subtype="element" match="ub:state">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																					<text fixtext="  "/>
																																					<template subtype="element" match="ub:postalcode">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																</children>
																															</tgridbody-rows>
																														</children>
																													</tgrid>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Service Location"/>
																						</children>
																					</paragraph>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties width="5%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="95%"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell/>
																											<tgridcell>
																												<children>
																													<tgrid>
																														<properties border="0"/>
																														<children>
																															<tgridbody-cols>
																																<children>
																																	<template subtype="source" match="XML">
																																		<children>
																																			<template subtype="element" match="ub:utilitybill">
																																				<children>
																																					<template subtype="element" match="ub:car">
																																						<children>
																																							<template subtype="element" match="ub:serviceaddress">
																																								<children>
																																									<tgridcol/>
																																								</children>
																																								<variables/>
																																							</template>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																															</tgridbody-cols>
																															<tgridbody-rows>
																																<children>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:addressee">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:street">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:city">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																					<text fixtext="  "/>
																																					<template subtype="element" match="ub:state">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																					<text fixtext="  "/>
																																					<template subtype="element" match="ub:postalcode">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																</children>
																															</tgridbody-rows>
																														</children>
																													</tgrid>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
													<newline/>
												</children>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/r.png)" background-repeat="repeat-y"/>
											</tgridcell>
										</children>
									</tgridrow>
									<tgridrow>
										<styles height="39px"/>
										<children>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/l.png)" background-repeat="repeat-y" vertical-align="top"/>
												<children>
													<image>
														<target>
															<fixtext value="images\EmeraldCity-1024\lcap.png"/>
														</target>
														<imagesource>
															<fixtext value="images\EmeraldCity-1024\lcap.png"/>
														</imagesource>
													</image>
												</children>
											</tgridcell>
											<tgridcell/>
											<tgridcell>
												<children>
													<tgrid>
														<properties border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="50%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties width="50%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h2">
																						<children>
																							<text fixtext="Bill Summary"/>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="large" font-weight="bolder"/>
																				<children>
																					<paragraph paragraphtag="h2">
																						<children>
																							<text fixtext="Due: "/>
																							<template subtype="source" match="XML">
																								<children>
																									<template subtype="element" match="ub:utilitybill">
																										<children>
																											<template subtype="element" match="ub:summary">
																												<children>
																													<template subtype="element" match="ub:duedate">
																														<children>
																															<content>
																																<format datatype="date"/>
																															</content>
																															<button>
																																<action>
																																	<datepicker/>
																																</action>
																															</button>
																														</children>
																														<variables/>
																													</template>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/r.png)" background-repeat="repeat-y"/>
											</tgridcell>
										</children>
									</tgridrow>
									<tgridrow>
										<children>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/l.png)" background-repeat="repeat-y"/>
											</tgridcell>
											<tgridcell/>
											<tgridcell>
												<children>
													<line/>
													<tgrid>
														<properties border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties valign="top" width="50%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties valign="top" width="50%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties width="30%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties valign="top" width="70%"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Bill Issued:">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<template subtype="source" match="XML">
																														<children>
																															<template subtype="element" match="ub:utilitybill">
																																<children>
																																	<template subtype="element" match="ub:summary">
																																		<children>
																																			<template subtype="element" match="ub:issuedate">
																																				<children>
																																					<content>
																																						<format datatype="date"/>
																																					</content>
																																					<button>
																																						<action>
																																							<datepicker/>
																																						</action>
																																					</button>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Bill Period: ">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<template subtype="source" match="XML">
																														<children>
																															<template subtype="element" match="ub:utilitybill">
																																<children>
																																	<template subtype="element" match="ub:summary">
																																		<children>
																																			<template subtype="element" match="ub:billperiodbegin">
																																				<children>
																																					<content>
																																						<format datatype="date"/>
																																					</content>
																																					<button>
																																						<action>
																																							<datepicker/>
																																						</action>
																																					</button>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																													<text fixtext=" to "/>
																													<template subtype="source" match="XML">
																														<children>
																															<template subtype="element" match="ub:utilitybill">
																																<children>
																																	<template subtype="element" match="ub:summary">
																																		<children>
																																			<template subtype="element" match="ub:billperiodend">
																																				<children>
																																					<content>
																																						<format datatype="date"/>
																																					</content>
																																					<button>
																																						<action>
																																							<datepicker/>
																																						</action>
																																					</button>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell/>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Late Charge: ">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<text fixtext="$"/>
																													<template subtype="source" match="XML">
																														<children>
																															<template subtype="element" match="ub:utilitybill">
																																<children>
																																	<template subtype="element" match="ub:summary">
																																		<children>
																																			<template subtype="element" match="ub:latepayment">
																																				<children>
																																					<template subtype="element" match="ub:amount">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																													<text fixtext="  after  "/>
																													<template subtype="source" match="XML">
																														<children>
																															<template subtype="element" match="ub:utilitybill">
																																<children>
																																	<template subtype="element" match="ub:summary">
																																		<children>
																																			<template subtype="element" match="ub:duedate">
																																				<children>
																																					<content>
																																						<format datatype="date"/>
																																					</content>
																																					<button>
																																						<action>
																																							<datepicker/>
																																						</action>
																																					</button>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties width="40%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="right" width="40%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="20%"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Utility Charges:">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<autocalc xpath="sum( $XML/ub:utilitybill/ub:summary/ub:currentcharges )"/>
																												</children>
																											</tgridcell>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Bill without Skyline: ">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<autocalc xpath="sum($XML/ub:utilitybill/ub:summary/ub:hypotheticalcharges)"/>
																												</children>
																											</tgridcell>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Skyline Charges:">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<autocalc xpath="sum($XML/ub:utilitybill/ub:summary/ub:skylinecharges)"/>
																												</children>
																											</tgridcell>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Your Savings:">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<autocalc xpath="sum($XML/ub:utilitybill/ub:summary/ub:hypotheticalcharges) - sum($XML/ub:utilitybill/ub:summary/ub:currentcharges) - sum($XML/ub:utilitybill/ub:summary/ub:skylinecharges)"/>
																												</children>
																											</tgridcell>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell/>
																											<tgridcell/>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Total Due:">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<text fixtext="$"/>
																													<template subtype="source" match="XML">
																														<children>
																															<template subtype="element" match="ub:utilitybill">
																																<children>
																																	<template subtype="element" match="ub:summary">
																																		<children>
																																			<template subtype="element" match="ub:totaldue">
																																				<children>
																																					<content>
																																						<styles font-weight="bold"/>
																																						<format datatype="decimal"/>
																																					</content>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
													<line/>
													<template subtype="source" match="XML">
														<children>
															<newline/>
															<paragraph>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Bill Details"/>
																		</children>
																	</paragraph>
																	<tgrid>
																		<properties border="0" width="100%"/>
																		<styles border-collapse="collapse"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol>
																						<properties align="right"/>
																					</tgridcol>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<tgrid>
																										<properties border="0" width="100%"/>
																										<styles border-collapse="collapse"/>
																										<children>
																											<tgridbody-cols>
																												<children>
																													<tgridcol/>
																												</children>
																											</tgridbody-cols>
																											<tgridbody-rows>
																												<children>
																													<tgridrow>
																														<children>
																															<tgridcell>
																																<children>
																																	<tgrid>
																																		<properties border="0" cellspacing="0px" width="100%"/>
																																		<children>
																																			<tgridbody-cols>
																																				<children>
																																					<tgridcol>
																																						<properties align="left" width="8%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties align="left" width="12%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties align="left" width="12%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties align="left" width="28%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties width="8%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties width="4%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties width="10%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties width="4%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties width="8%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties width="8%"/>
																																					</tgridcol>
																																				</children>
																																			</tgridbody-cols>
																																			<tgridbody-rows>
																																				<children>
																																					<tgridrow>
																																						<children>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																								<children>
																																									<text fixtext="Service">
																																										<styles font-weight="bold"/>
																																									</text>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																								<children>
																																									<text fixtext="Rate">
																																										<styles font-weight="bold"/>
																																									</text>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																								<children>
																																									<text fixtext="Charge">
																																										<styles font-weight="bold"/>
																																									</text>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																								<children>
																																									<text fixtext="Description">
																																										<styles font-weight="bold"/>
																																									</text>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																								<children>
																																									<text fixtext="Quantity">
																																										<styles font-weight="bold"/>
																																									</text>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																								<children>
																																									<text fixtext="Rate">
																																										<styles font-weight="bold"/>
																																									</text>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																								<children>
																																									<text fixtext="Amount">
																																										<styles font-weight="bold"/>
																																									</text>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid" border-right-color="black" border-right-style="solid" border-right-width="1px"/>
																																							</tgridcell>
																																						</children>
																																					</tgridrow>
																																				</children>
																																			</tgridbody-rows>
																																		</children>
																																	</tgrid>
																																</children>
																															</tgridcell>
																														</children>
																													</tgridrow>
																													<tgridrow>
																														<children>
																															<tgridcell>
																																<children>
																																	<tgrid>
																																		<properties border="0" width="100%"/>
																																		<styles border-collapse="collapse"/>
																																		<children>
																																			<tgridbody-cols>
																																				<children>
																																					<tgridcol>
																																						<properties align="left" width="8%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties align="left" width="12%"/>
																																					</tgridcol>
																																					<tgridcol>
																																						<properties align="right" width="80%"/>
																																					</tgridcol>
																																				</children>
																																			</tgridbody-cols>
																																			<tgridbody-rows>
																																				<children>
																																					<template subtype="element" match="ub:utilitybill">
																																						<children>
																																							<template subtype="element" match="ub:details">
																																								<children>
																																									<tgridrow>
																																										<properties valign="top"/>
																																										<children>
																																											<tgridcell>
																																												<children>
																																													<template subtype="attribute" match="service">
																																														<children>
																																															<content/>
																																														</children>
																																														<variables/>
																																													</template>
																																												</children>
																																											</tgridcell>
																																											<tgridcell>
																																												<children>
																																													<template subtype="element" match="ub:rateschedule">
																																														<children>
																																															<content/>
																																														</children>
																																														<variables/>
																																													</template>
																																												</children>
																																											</tgridcell>
																																											<tgridcell>
																																												<children>
																																													<tgrid>
																																														<properties border="0" width="100%"/>
																																														<styles border-collapse="collapse"/>
																																														<children>
																																															<tgridbody-cols>
																																																<children>
																																																	<tgridcol/>
																																																</children>
																																															</tgridbody-cols>
																																															<tgridbody-rows>
																																																<children>
																																																	<tgridrow>
																																																		<children>
																																																			<tgridcell>
																																																				<children>
																																																					<tgrid>
																																																						<properties border="0" width="100%"/>
																																																						<styles border-collapse="collapse" font-size="smaller"/>
																																																						<children>
																																																							<tgridbody-cols>
																																																								<children>
																																																									<tgridcol>
																																																										<properties align="left" valign="top" width="15%"/>
																																																									</tgridcol>
																																																									<tgridcol>
																																																										<properties align="right" width="85%"/>
																																																									</tgridcol>
																																																								</children>
																																																							</tgridbody-cols>
																																																							<tgridbody-rows>
																																																								<children>
																																																									<template subtype="element" match="ub:chargegroup">
																																																										<children>
																																																											<tgridrow>
																																																												<children>
																																																													<tgridcell>
																																																														<children>
																																																															<template subtype="attribute" match="type">
																																																																<children>
																																																																	<content/>
																																																																</children>
																																																																<variables/>
																																																															</template>
																																																														</children>
																																																													</tgridcell>
																																																													<tgridcell>
																																																														<children>
																																																															<tgrid>
																																																																<properties border="0" width="100%"/>
																																																																<styles border-collapse="collapse"/>
																																																																<children>
																																																																	<tgridbody-cols>
																																																																		<children>
																																																																			<tgridcol/>
																																																																		</children>
																																																																	</tgridbody-cols>
																																																																	<tgridbody-rows>
																																																																		<children>
																																																																			<tgridrow>
																																																																				<children>
																																																																					<tgridcell>
																																																																						<children>
																																																																							<tgrid>
																																																																								<properties border="0" width="100%"/>
																																																																								<styles border-collapse="collapse"/>
																																																																								<children>
																																																																									<tgridbody-cols>
																																																																										<children>
																																																																											<tgridcol>
																																																																												<properties align="left" width="40%"/>
																																																																											</tgridcol>
																																																																											<tgridcol>
																																																																												<properties align="right" width="12%"/>
																																																																											</tgridcol>
																																																																											<tgridcol>
																																																																												<properties align="left" width="8%"/>
																																																																											</tgridcol>
																																																																											<tgridcol>
																																																																												<properties align="right" width="12%"/>
																																																																											</tgridcol>
																																																																											<tgridcol>
																																																																												<properties align="left" width="8%"/>
																																																																											</tgridcol>
																																																																											<tgridcol>
																																																																												<properties align="right" width="12%"/>
																																																																											</tgridcol>
																																																																											<tgridcol>
																																																																												<properties width="8%"/>
																																																																											</tgridcol>
																																																																										</children>
																																																																									</tgridbody-cols>
																																																																									<tgridbody-rows>
																																																																										<children>
																																																																											<template subtype="element" match="ub:charges">
																																																																												<children>
																																																																													<template subtype="element" match="ub:charge">
																																																																														<children>
																																																																															<tgridrow>
																																																																																<children>
																																																																																	<tgridcell>
																																																																																		<children>
																																																																																			<template subtype="element" match="ub:description">
																																																																																				<children>
																																																																																					<content/>
																																																																																				</children>
																																																																																				<variables/>
																																																																																			</template>
																																																																																		</children>
																																																																																	</tgridcell>
																																																																																	<tgridcell>
																																																																																		<children>
																																																																																			<template subtype="element" match="ub:quantity">
																																																																																				<children>
																																																																																					<content/>
																																																																																				</children>
																																																																																				<variables/>
																																																																																			</template>
																																																																																		</children>
																																																																																	</tgridcell>
																																																																																	<tgridcell>
																																																																																		<children>
																																																																																			<template subtype="element" match="ub:quantity">
																																																																																				<children>
																																																																																					<template subtype="attribute" match="units">
																																																																																						<children>
																																																																																							<content/>
																																																																																						</children>
																																																																																						<variables/>
																																																																																					</template>
																																																																																				</children>
																																																																																				<variables/>
																																																																																			</template>
																																																																																		</children>
																																																																																	</tgridcell>
																																																																																	<tgridcell>
																																																																																		<children>
																																																																																			<text fixtext=" "/>
																																																																																			<template subtype="element" match="ub:rate">
																																																																																				<children>
																																																																																					<content/>
																																																																																				</children>
																																																																																				<variables/>
																																																																																			</template>
																																																																																		</children>
																																																																																	</tgridcell>
																																																																																	<tgridcell>
																																																																																		<children>
																																																																																			<template subtype="element" match="ub:rate">
																																																																																				<children>
																																																																																					<template subtype="attribute" match="units">
																																																																																						<children>
																																																																																							<content/>
																																																																																						</children>
																																																																																						<variables/>
																																																																																					</template>
																																																																																				</children>
																																																																																				<variables/>
																																																																																			</template>
																																																																																		</children>
																																																																																	</tgridcell>
																																																																																	<tgridcell>
																																																																																		<properties align="right"/>
																																																																																		<children>
																																																																																			<template subtype="element" match="ub:total">
																																																																																				<children>
																																																																																					<content>
																																																																																						<format datatype="decimal"/>
																																																																																					</content>
																																																																																				</children>
																																																																																				<variables/>
																																																																																			</template>
																																																																																		</children>
																																																																																	</tgridcell>
																																																																																	<tgridcell/>
																																																																																</children>
																																																																															</tgridrow>
																																																																														</children>
																																																																														<variables/>
																																																																													</template>
																																																																												</children>
																																																																												<variables/>
																																																																											</template>
																																																																										</children>
																																																																									</tgridbody-rows>
																																																																								</children>
																																																																							</tgrid>
																																																																						</children>
																																																																					</tgridcell>
																																																																				</children>
																																																																			</tgridrow>
																																																																			<tgridrow>
																																																																				<children>
																																																																					<tgridcell>
																																																																						<children>
																																																																							<line/>
																																																																							<autocalc xpath="sum(ub:charges/ub:charge/ub:total )">
																																																																								<styles font-style="italic"/>
																																																																							</autocalc>
																																																																						</children>
																																																																					</tgridcell>
																																																																				</children>
																																																																			</tgridrow>
																																																																		</children>
																																																																	</tgridbody-rows>
																																																																</children>
																																																															</tgrid>
																																																														</children>
																																																													</tgridcell>
																																																												</children>
																																																											</tgridrow>
																																																										</children>
																																																										<variables/>
																																																									</template>
																																																								</children>
																																																							</tgridbody-rows>
																																																						</children>
																																																					</tgrid>
																																																				</children>
																																																			</tgridcell>
																																																		</children>
																																																	</tgridrow>
																																																	<tgridrow>
																																																		<children>
																																																			<tgridcell>
																																																				<children>
																																																					<line/>
																																																					<text fixtext=" $"/>
																																																					<autocalc xpath="sum( chargegroup/charges/charge/total )">
																																																						<styles font-style="normal" font-weight="bold"/>
																																																					</autocalc>
																																																				</children>
																																																			</tgridcell>
																																																		</children>
																																																	</tgridrow>
																																																</children>
																																															</tgridbody-rows>
																																														</children>
																																													</tgrid>
																																												</children>
																																											</tgridcell>
																																										</children>
																																									</tgridrow>
																																								</children>
																																								<variables/>
																																							</template>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridbody-rows>
																																		</children>
																																	</tgrid>
																																</children>
																															</tgridcell>
																														</children>
																													</tgridrow>
																												</children>
																											</tgridbody-rows>
																										</children>
																									</tgrid>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridbody-rows>
																			<tgridfooter-rows>
																				<children>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<text fixtext="Total charges $"/>
																									<autocalc xpath="sum(ub:utilitybill/ub:details/ub:chargegroup/ub:charges/ub:charge/ub:total )">
																										<styles font-style="italic" font-weight="bold"/>
																									</autocalc>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridfooter-rows>
																		</children>
																	</tgrid>
																</children>
															</paragraph>
															<paragraph>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Measured Usage"/>
																		</children>
																	</paragraph>
																	<tgrid>
																		<properties border="0" width="100%"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol>
																						<properties width="50%"/>
																					</tgridcol>
																				</children>
																			</tgridbody-cols>
																			<tgridheader-rows>
																				<children>
																					<tgridrow>
																						<styles height="0.19in"/>
																						<children>
																							<tgridcell>
																								<children>
																									<tgrid>
																										<properties border="0" cellspacing="0" width="100%"/>
																										<children>
																											<tgridbody-cols>
																												<children>
																													<tgridcol>
																														<properties align="left" width="25%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="left" width="50%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="right" width="15%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="left" width="10%"/>
																													</tgridcol>
																												</children>
																											</tgridbody-cols>
																											<tgridbody-rows>
																												<children>
																													<tgridrow>
																														<children>
																															<tgridcell>
																																<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																<children>
																																	<text fixtext="Meter Register"/>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																<children>
																																	<text fixtext="Description"/>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																																<children>
																																	<text fixtext="Total"/>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid" border-right="1px" border-right-color="black" border-right-style="solid"/>
																															</tgridcell>
																														</children>
																													</tgridrow>
																												</children>
																											</tgridbody-rows>
																										</children>
																									</tgrid>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridheader-rows>
																			<tgridbody-rows>
																				<children>
																					<template subtype="element" match="ub:utilitybill">
																						<children>
																							<template subtype="element" match="ub:measuredusage">
																								<children>
																									<template subtype="element" match="ub:meter">
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<tgrid>
																																<properties border="0" width="100%"/>
																																<styles font-size="smaller"/>
																																<children>
																																	<tgridbody-cols>
																																		<children>
																																			<tgridcol>
																																				<properties align="right"/>
																																			</tgridcol>
																																		</children>
																																	</tgridbody-cols>
																																	<tgridbody-rows>
																																		<children>
																																			<tgridrow>
																																				<children>
																																					<tgridcell>
																																						<children>
																																							<tgrid>
																																								<properties border="0" width="100%"/>
																																								<children>
																																									<tgridbody-cols>
																																										<children>
																																											<tgridcol>
																																												<properties align="left" width="25%"/>
																																											</tgridcol>
																																											<tgridcol>
																																												<properties align="left" width="50%"/>
																																											</tgridcol>
																																											<tgridcol>
																																												<properties align="right" width="15%"/>
																																											</tgridcol>
																																											<tgridcol>
																																												<properties align="left" width="10%"/>
																																											</tgridcol>
																																										</children>
																																									</tgridbody-cols>
																																									<tgridbody-rows>
																																										<children>
																																											<template subtype="element" match="ub:register">
																																												<children>
																																													<tgridrow>
																																														<children>
																																															<tgridcell>
																																																<children>
																																																	<template subtype="element" match="ub:identifier">
																																																		<children>
																																																			<content/>
																																																		</children>
																																																		<variables/>
																																																	</template>
																																																</children>
																																															</tgridcell>
																																															<tgridcell>
																																																<children>
																																																	<template subtype="element" match="ub:description">
																																																		<children>
																																																			<content/>
																																																		</children>
																																																		<variables/>
																																																	</template>
																																																</children>
																																															</tgridcell>
																																															<tgridcell>
																																																<children>
																																																	<template subtype="element" match="ub:total">
																																																		<children>
																																																			<content>
																																																				<format datatype="decimal"/>
																																																			</content>
																																																		</children>
																																																		<variables/>
																																																	</template>
																																																</children>
																																															</tgridcell>
																																															<tgridcell>
																																																<children>
																																																	<template subtype="element" match="ub:units">
																																																		<children>
																																																			<content/>
																																																		</children>
																																																		<variables/>
																																																	</template>
																																																</children>
																																															</tgridcell>
																																														</children>
																																													</tgridrow>
																																												</children>
																																												<variables/>
																																											</template>
																																										</children>
																																									</tgridbody-rows>
																																								</children>
																																							</tgrid>
																																						</children>
																																					</tgridcell>
																																				</children>
																																			</tgridrow>
																																		</children>
																																	</tgridbody-rows>
																																</children>
																															</tgrid>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																	<newline/>
																</children>
															</paragraph>
														</children>
														<variables/>
													</template>
												</children>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/r.png)" background-repeat="repeat-y"/>
											</tgridcell>
										</children>
									</tgridrow>
									<tgridrow>
										<styles height="66px"/>
										<children>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/bl.png)" background-repeat="no-repeat"/>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/b.png)" background-repeat="repeat-x"/>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/b.png)" background-repeat="repeat-x"/>
											</tgridcell>
											<tgridcell>
												<styles background-image="url(file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity-1024/br.png)" background-repeat="no-repeat"/>
											</tgridcell>
										</children>
									</tgridrow>
								</children>
							</tgridbody-rows>
						</children>
					</tgrid>
					<newline/>
					<newline/>
				</children>
			</globaltemplate>
		</children>
	</mainparts>
	<globalparts/>
	<pagelayout>
		<properties paperheight="11.69in" paperwidth="8.27in"/>
	</pagelayout>
	<designfragments/>
</structure>
