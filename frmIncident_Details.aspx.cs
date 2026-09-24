using System;
using System.Data;
using System.Configuration;
using System.Collections;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS_Common;
using EBS.Classes;
using EBS_Common.Classes.Misc;
using EBS_Common.Classes;
using System.IO;
using CrystalDecisions.CrystalReports.Engine;
using CrystalDecisions.Shared;
using System.Collections.Generic;
using System.Net;
using System.Drawing;
using System.Data.OleDb;
using System.Collections.Generic;
using EBS_Reports.EOS; 



public partial class Fleet_Personnel_frmIncident_Details : System.Web.UI.Page
{
    # region User defined variables
    //protected Common_DataRetrival _Common_DataRetrival;
    protected DataSet Ds;
    DataSet DsIncident_Descr = new DataSet();
    SqlConnection Conn;
    SqlDataAdapter Da;
    string strConString = "";
    string strSql = "";
    string ErrorString = "";
    int intImgCnt = 0;
    string[] IMG = new string[10];
    Button[] btnEnableDisable;
    Int16 intMenu_id;
    Int32 intUser_Id;
    public DataTable DtIncident_Img_Path = new DataTable();
    #endregion

    protected string strDebugModeYN = ConfigurationSettings.AppSettings["DebugModeYN"];
    protected void Page_Load(object sender, EventArgs e)
    {
        # region Code to Enable / Disable Button
        #region Adding buttons which needs to pass
        //System.Web.UI.WebControls.Button[] btnEnableDisable = new System.Web.UI.WebControls.Button[5];
        //btnEnableDisable[0] = btnAdd;
        //btnEnableDisable[1] = btnUpdate;
        //btnEnableDisable[2] = btnSearch;
        //btnEnableDisable[3] = btnDelete;
        //btnEnableDisable[4] = btnPrint;

        var list = new List<Button>();
        list.Add(btnAdd);
        list.Add(btnUpdate);
        list.Add(btnSearch);
        list.Add(btnPrint);
        list.Add(btnDelete);
        btnEnableDisable = list.ToArray();
        #endregion

        strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();

        #region 1st Parameter is always Menu Id
        string strScramble = Request.QueryString["A"];
        string strdeCrypt = clsMiscellaneous.decryptQueryString(strScramble.Replace(" ", "+"));
        intMenu_id = Convert.ToInt16(strdeCrypt);
        intUser_Id = Convert.ToInt32(Session["User_Id"].ToString());
        # endregion

        if (!IsPostBack)
        {
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString,"Add");
            Bind_Images_File_Upload();
        }
        #endregion

        tbRig_Incident_No.Focus();

        #region Depending on selected Employee, fetch the values of Rank field & fill the textboxes

        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
            Get_Data_For_Edit();
            tbPostbackFlag_Hidden.Value = "";
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");

        }
        else if (tbPostbackFlag_Hidden.Value == "CURRENCY")
        {
            CalculateBaseCurrency();
            tbPostbackFlag_Hidden.Value = "";
        }
        else if (tbPostbackFlag_Hidden.Value == "RIG")
        {
            tbPostbackFlag_Hidden.Value = "";
            tbIncident_Date.Text = "";
            tbIncident_Time.Text = "";
            tbIncident_No.Text = "";
            tbUnit_Name.Text = "";
        }
        else if (tbPostbackFlag_Hidden.Value == "INCIDENT_DATE_CHANGE")
        {
            //Set_Max_Incident_No();
            GetCountry_Well();
            tbPostbackFlag_Hidden.Value = "";
        }
        else if (tbPostbackFlag_Hidden.Value == "FSEMPLOYEE")
        {
            Get_Employee_Rank();
            tbPostbackFlag_Hidden.Value = "";
        }
        /* Do not delete : Code for automated Rig data upload.  To be enabled later.
        else if (tbPostbackFlag_Hidden.Value == "WKG_INCIDENT_DTL")
        {
            tbPostbackFlag_Hidden.Value = "";
            Get_Wkg_Incident_Dtl();
        }
        */
        #endregion


    }
    public void Get_Employee_Rank()
    {
        Conn = new SqlConnection(strConString);
        try
        {
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            DataSet Ds;
            SqlDataAdapter Da;
            Ds = new DataSet();
            Da = new SqlDataAdapter("select " + OI.Def + "Fnc_Get_Col_Value('" + OI.Def + "Mst_Fs_Employee',@Fs_Emp_Id,'RANK')Rank_Id, " + OI.Glo + "fnc_get_col_value('" + OI.Glo + "Mst_Rank'," + OI.Def + "fnc_get_col_value('" + OI.Def + "Mst_Fs_Employee',@Fs_Emp_Id,'RANK'),'name')Rank_Name", Conn);
            Da.SelectCommand.CommandType = CommandType.Text;
            
            Da.SelectCommand.Parameters.Add("@Fs_Emp_Id", SqlDbType.Int).Value = Convert.ToInt32(tbFs_Emp_Id_Hidden.Value);

            Da.Fill(Ds, "Data_Rank_Category");

            tbRptd_By_Rank_Id_Hidden.Value = Ds.Tables["Data_Rank_Category"].Rows[0]["Rank_Id"].ToString();
            tbRptd_By_Rank_Name.Text = Ds.Tables["Data_Rank_Category"].Rows[0]["Rank_Name"].ToString();
            tbComments.Focus();
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);

        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);

        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
            }

        }
    }

    private void InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum Type)
    {
        clsIncident_Details _ObjMaster = new clsIncident_Details(strConString);


        // Changes by vipin Add Part_Of_Body_Injured
        // _ObjMaster.Part_Of_Body_Injured = ddlPart_Of_Body_Injured.SelectedValue;
        if (tbPart_Of_Body_Id_Hidden_1.Value != "")
        {
            _ObjMaster.Part_Of_Body_Id_1 = Convert.ToByte(tbPart_Of_Body_Id_Hidden_1.Value);
        }
        else
        {
            _ObjMaster.Part_Of_Body_Id_1 = null;
        }

        if (tbPart_Of_Body_Id_Hidden_2.Value != "")
        {
            _ObjMaster.Part_Of_Body_Id_2 = Convert.ToByte(tbPart_Of_Body_Id_Hidden_2.Value);
        }
        else
        {
            _ObjMaster.Part_Of_Body_Id_2 = null;
        }

        if (tbPart_Of_Body_Id_Hidden_3.Value != "")
        {
            _ObjMaster.Part_Of_Body_Id_3 = Convert.ToByte(tbPart_Of_Body_Id_Hidden_3.Value);
        }
        else
        {
            _ObjMaster.Part_Of_Body_Id_3 = null;
        }

        if (tbPart_Of_Body_Id_Hidden_4.Value != "")
        {
            _ObjMaster.Part_Of_Body_Id_4 = Convert.ToByte(tbPart_Of_Body_Id_Hidden_4.Value);
        }
        else
        {
            _ObjMaster.Part_Of_Body_Id_4 = null;
        }

        _ObjMaster.Rig_Incident_No = tbRig_Incident_No.Text;



        if (tbRig_Id_Hidden.Value != "")
            _ObjMaster.Rig_Id = Convert.ToInt16(tbRig_Id_Hidden.Value);
        else
            _ObjMaster.Rig_Id = null;

        if (tbUnit_Name.Text != "")
            _ObjMaster.Unit_Name = tbUnit_Name.Text;
        else
            _ObjMaster.Unit_Name = null;

        _ObjMaster.Incident_Date = tbIncident_Date.Text;
        _ObjMaster.Incident_Time = tbIncident_Time.Text;

        _ObjMaster.Incident_Reported_Dt = tbIncident_Reported_Dt.Text;
        _ObjMaster.Incident_Reported_Time = tbIncident_Reported_Time.Text;

        if (tbCountry_Id_Hidden.Value != "")
            _ObjMaster.Country_Id = Convert.ToInt16(tbCountry_Id_Hidden.Value);
        else
            _ObjMaster.Country_Id = null;

        if (tbOperator_Id_Hidden.Value != "")
            _ObjMaster.Operator_Id = Convert.ToInt16(tbOperator_Id_Hidden.Value);
        else
            _ObjMaster.Operator_Id = null;


        _ObjMaster.Well_No = tbWell_No.Text;
        _ObjMaster.Drilling_Superintendent = tbDrilling_Superintendent.Text;
        _ObjMaster.Safety_Officer = tbSafety_Officer.Text;
        _ObjMaster.Incident_Type_Id = Convert.ToByte(tbIncident_Type_Id_Hidden.Value);

        _ObjMaster.Incident_Severity = ddlIncident_Severity_Actual.SelectedValue;
        _ObjMaster.Incident_Severity_Potential = ddlIncident_Severity_Potential.SelectedValue;



        #region Section  Injury
        _ObjMaster.Person_Injured = ddlPerson_Injured.SelectedValue;

        //Value="N" EOSIL
        //Value="Y" TP Contractors

        if (ddlPerson_Injured.SelectedValue == "N")///IF Person_Injured= "N" then Pass Null in Third Party
            _ObjMaster.Third_Party = null;
        else
            _ObjMaster.Third_Party = ddlThird_Party.SelectedValue;

        _ObjMaster.Incident_Party = ddlIncident_Party.SelectedValue;


        if (ddlThird_Party.SelectedValue == "0" || ddlThird_Party.SelectedValue == "1")///IF third party is Selected then Contractor is Compusary
            _ObjMaster.Contractor_Id = Convert.ToInt16(tbContractor_Id_Hidden.Value);
        else
            _ObjMaster.Contractor_Id = null;


    
        _ObjMaster.Emp_Name = tbEmp_Name.Text;

        if (tbRank_Id_Hidden.Value != "")
            _ObjMaster.Rank_Id = Convert.ToByte(tbRank_Id_Hidden.Value);
        else
            _ObjMaster.Rank_Id = null;

        if (tbTotal_Rig_Exp_Months.Text != "")
            _ObjMaster.Total_Rig_Exp_Months = Convert.ToInt16(tbTotal_Rig_Exp_Months.Text);
        else
            _ObjMaster.Total_Rig_Exp_Months = null;
        #endregion


        _ObjMaster.Incident_Descr = tbIncident_Descr.Text;
        _ObjMaster.Immediate_Incident_Cause_Id_1 = Convert.ToByte(tbImmediate_Incident_Cause_Id_1_Hidden.Value);

        if (tbImmediate_Incident_Cause_Id_2_Hidden.Value != "")
            _ObjMaster.Immediate_Incident_Cause_Id_2 = Convert.ToByte(tbImmediate_Incident_Cause_Id_2_Hidden.Value);
        else
            _ObjMaster.Immediate_Incident_Cause_Id_2 = null;

        _ObjMaster.Immediate_Cause_Descr = tbImmediate_Cause_Descr.Text;

        _ObjMaster.Rig_Operation_Id = Convert.ToByte(tbRig_Operation_Id_Hidden.Value);

        _ObjMaster.Work_Location_Id = Convert.ToByte(tbWork_Location_Id_Hidden.Value);

        _ObjMaster.Contact_Expo_Type_Id = Convert.ToByte(tbContact_Expo_Type_Id_Hidden.Value);

        if (tbCorrective_Action.Text != "")
            _ObjMaster.Corrective_Action = tbCorrective_Action.Text;
        else
            _ObjMaster.Corrective_Action = null;

        if (tbPreventive_Action.Text != "")
            _ObjMaster.Preventive_Action = tbPreventive_Action.Text;
        else
            _ObjMaster.Preventive_Action = null;

        if (String.IsNullOrEmpty(tbNPT_Hrs_Loss.Text))
            _ObjMaster.NPT_Hrs_Loss = null;
        else
            _ObjMaster.NPT_Hrs_Loss = Convert.ToDecimal(tbNPT_Hrs_Loss.Text);

        if (String.IsNullOrEmpty(tbManhours_Loss.Text.ToString()))
            _ObjMaster.Manhours_Loss = null;
        else
            _ObjMaster.Manhours_Loss = Convert.ToDecimal(tbManhours_Loss.Text);

        if (String.IsNullOrEmpty(tbFinancial_Loss_Amt.Text.ToString()))
            _ObjMaster.Financial_Loss_Amt = null;
        else
            _ObjMaster.Financial_Loss_Amt = Convert.ToInt32(tbFinancial_Loss_Amt.Text);

        //Changes Commeted 09/July/2013
        //if (String.IsNullOrEmpty(tbFinancial_Loss_Currency_Id_Hidden.Value))
        //    _ObjMaster.Financial_Loss_Amt = null;
        //else
        //    _ObjMaster.Financial_Loss_Currency_Id = Convert.ToByte(tbFinancial_Loss_Currency_Id_Hidden.Value);

        if (!String.IsNullOrEmpty(tbFinancial_Loss_Currency_Id_Hidden.Value))
            _ObjMaster.Financial_Loss_Currency_Id = Convert.ToByte(tbFinancial_Loss_Currency_Id_Hidden.Value);
        else
            _ObjMaster.Financial_Loss_Currency_Id = null;

        _ObjMaster.Exchange_Rate = null;
        _ObjMaster.Financial_Loss_BC_Amt = null;

        //Changes Commeted 09/July/2013
        //if (String.IsNullOrEmpty(tbExchange_Rate.Text))
        //    _ObjMaster.Exchange_Rate = null;
        //else
        //    _ObjMaster.Exchange_Rate = Convert.ToDecimal(tbExchange_Rate.Text);

        //if (String.IsNullOrEmpty(tbFinancial_Loss_Amt.Text) || (String.IsNullOrEmpty(tbExchange_Rate.Text)))
        //    _ObjMaster.Financial_Loss_BC_Amt = null;
        //else
        //    _ObjMaster.Financial_Loss_BC_Amt = Convert.ToInt32(Convert.ToDecimal(tbExchange_Rate.Text) * Convert.ToDecimal(tbFinancial_Loss_Amt.Text));

        if (tbEmp_Name.Text != "")
            _ObjMaster.Emp_Name = tbEmp_Name.Text;
        else
            _ObjMaster.Emp_Name = null;


        if (!String.IsNullOrEmpty(tbRank_Id_Hidden.Value))
            _ObjMaster.Rank_Id = Convert.ToByte(tbRank_Id_Hidden.Value);
        else
            _ObjMaster.Rank_Id = null;

        if (!String.IsNullOrEmpty(tbReported_By.Text))
            _ObjMaster.Reported_By = tbReported_By.Text;
        else
            _ObjMaster.Reported_By = null;


        if (!String.IsNullOrEmpty(tbRptd_By_Rank_Id_Hidden.Value))
            _ObjMaster.Rptd_By_Rank_Id = Convert.ToByte(tbRptd_By_Rank_Id_Hidden.Value);
        else
            _ObjMaster.Rptd_By_Rank_Id = null;

        if (!String.IsNullOrEmpty(tbComments.Text))
            _ObjMaster.Comments = tbComments.Text;
        else
            _ObjMaster.Comments = null;
           
        //Sumit DMS path code.........
        string strFolderName = "";

        if (tbDMS_Folder_Name.Text == "")
        {
            strFolderName = "*";///If Folder Name is BLANK then Save it as "*"
        }
        else
        {
            strFolderName = tbDMS_Folder_Name.Text;
        }

        if (tbDMS_Path_QHSE.Text != "")
            _ObjMaster.DMS_Path_QHSE = tbDMS_Path_QHSE.Text + "" + strFolderName + "" + tbResume_File_Name.Text;
        else
            _ObjMaster.DMS_Path_QHSE = null;

        ///Used in Add / Update
        ///as changes on 17/02/2017
        //_ObjMaster.Incident_No = Convert.ToByte(tbIncident_No.Text);


        switch (Type)
        {
            case EBS_Common.Classes.InsertUpdateData_Enum.Insert:
                {


                    SqlTransaction trDML;
                    Conn = new SqlConnection(strConString);

                    if (Conn.State == ConnectionState.Closed)
                        Conn.Open(); 

                    trDML = Conn.BeginTransaction();
                    try
                    {

                        _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                        _ObjMaster.InsertMe(ref grdInc_Images, ref trDML, ref Conn);

                        tbIncident_Id_Hidden.Value = _ObjMaster.Incident_Id.ToString();

                        ////after successfully adding of recorfsd send the mail to the mentioned 
                        #region SEND MAIL


                        #region Step 2 : Send to mentioned emails ids
                        string strTo = "";
                        string strCc = "";
                        string strBcc = "";
                        string strSubject = "";
                        string strRead_Receipt_To = "";


                        SqlCommand cmd = new SqlCommand(OI.Def + "Prc_Rig_To_Email_Mapping_Email_Config", Conn, trDML);
                        cmd.CommandType = CommandType.StoredProcedure;

                        cmd.Parameters.Add(new SqlParameter("Alert_Id", SqlDbType.TinyInt));
                        //this is diffrent as Mail mut be sent to the mentioned rigs email ids
                        //plus form the generatl list of mail lert dtl table
                        cmd.Parameters["Alert_Id"].Value = 240;


                        cmd.Parameters.Add(new SqlParameter("Rig_Id", SqlDbType.Int));
                        cmd.Parameters["Rig_Id"].Value = Convert.ToInt32(tbRig_Id_Hidden.Value);

                        cmd.Parameters.Add(new SqlParameter("strCurr_Logged_In_User_Id", SqlDbType.Int));                        
                        cmd.Parameters["strCurr_Logged_In_User_Id"].Value = Convert.ToInt32(Session["User_Id"].ToString());
                        
                        cmd.Parameters.Add(new SqlParameter("Addressee_Type_Curr_Logged_In_User_Id", SqlDbType.VarChar)); 
                        cmd.Parameters["Addressee_Type_Curr_Logged_In_User_Id"].Value = "C";

                        cmd.Parameters.Add(new SqlParameter("Include_Mail_Alert_Dtl_Emails", SqlDbType.VarChar)); 
                        cmd.Parameters["Include_Mail_Alert_Dtl_Emails"].Value = "Y";                         
                        
                        cmd.Parameters.Add(new SqlParameter("strTo_Recipients", SqlDbType.VarChar, 5000));
                        cmd.Parameters["strTo_Recipients"].Direction = ParameterDirection.Output;

                        cmd.Parameters.Add(new SqlParameter("strCc_Recipients", SqlDbType.VarChar, 5000));
                        cmd.Parameters["strCc_Recipients"].Direction = ParameterDirection.Output;

                        cmd.Parameters.Add(new SqlParameter("strBcc_Recipients", SqlDbType.VarChar, 5000));
                        cmd.Parameters["strBcc_Recipients"].Direction = ParameterDirection.Output;

                        cmd.Parameters.Add(new SqlParameter("strMail_Subject", SqlDbType.VarChar, 5000));
                        cmd.Parameters["strMail_Subject"].Direction = ParameterDirection.Output;


                        cmd.Parameters.Add(new SqlParameter("strRead_Receipt_Recipient", SqlDbType.VarChar, 5000));
                        cmd.Parameters["strRead_Receipt_Recipient"].Direction = ParameterDirection.Output;

                        cmd.ExecuteNonQuery();

                        strTo = cmd.Parameters["strTo_Recipients"].Value.ToString();
                        if (!string.IsNullOrEmpty(strTo))
                            strTo = strTo.Substring(0, strTo.Length - 1);

                        strCc = cmd.Parameters["strCc_Recipients"].Value.ToString();
                        if (!string.IsNullOrEmpty(strCc))
                            strCc = strCc.Substring(0, strCc.Length - 1);

                        strBcc = cmd.Parameters["strBcc_Recipients"].Value.ToString();
                        if (!string.IsNullOrEmpty(strBcc))
                            strBcc = strBcc.Substring(0, strBcc.Length - 1);



                        ///Mail_Subject from the Mail_Alert_Dtl table
                        strSubject = cmd.Parameters["strMail_Subject"].Value.ToString();

                        ///Take the Read Receipt Email
                        strRead_Receipt_To = cmd.Parameters["strRead_Receipt_Recipient"].Value.ToString();

                        #endregion



                        #region Create Pdf Files First
                        string strFile_Path = Call_Report("Send_Email", ref trDML, ref Conn);
                        if (strFile_Path.Contains("Err:"))
                        {
                            throw new Exception(strFile_Path.Replace("Err:", ""));

                            /// ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", "alert('No Data for this criterion')", true);

                        }
                        #endregion

                        //as this section is commom for all the roles
                        String strBody = Get_Email_Body("ADD");

                        if (ConfigurationManager.ConnectionStrings["DebugModeYN"].ToString() == "Y")
                        {
                            strBody += "TO : " + strTo + " | CC: " + strCc + " | BCC: " + strBcc;
                        }

                        #region  Create Body Containt of Mail...
                        strBody = strBody + "<br/><br/><br/><b>*&nbsp;<font color='#23238E'" + "style=" + Convert.ToChar(34) + "font-family: Arial ;font-size: 10pt" + Convert.ToChar(34) + " >" + clsSystem_Generic_Info.Automail_Footer.ToString() + "</font></b>";
                        #endregion


                        #region common portion of the SEND MAIL
                        ///Common to the all roles
                        EBS_Common.Classes.Mail.clsSendMail objSend_Mail = new EBS_Common.Classes.Mail.clsSendMail();
                        string strDebugModeYN = ConfigurationManager.ConnectionStrings["DebugModeYN"].ToString();
                        objSend_Mail._To = strTo;
                        objSend_Mail._CC = strCc;
                        objSend_Mail._BCC = strBcc;
                        objSend_Mail._Debug_Email_Id = "savita.bodake@acerinox.co.in";

                        ///changes on 13 March 2015 ,Due to this parameter FROM address will be logged in user.
                        objSend_Mail._Mail_From_Address_Of_Logged_In_User = "Y";

                        ///If Employee Email Id is Empty then Display Err Msg
                        if (string.IsNullOrEmpty(strTo.ToString().Trim()))
                        {
                            ErrorString = "Mail recipient has not been defined .|";
                            throw new Exception(ErrorString);
                        }
                        else
                        {
                            #region Send Mail
                            objSend_Mail._Subject = strSubject;
                            objSend_Mail._BodyFormat = true;
                            objSend_Mail._Body = strBody;
                            objSend_Mail._Attach = strFile_Path;// Server.MapPath("~/TempReports") + "\\" + strFile_Path;
                            objSend_Mail.SendMail(ConfigurationManager.ConnectionStrings["DebugModeYN"].ToString(), strConString);///If Error occur will handlled in catch (Exception exep)                                                             

                            #endregion
                        }



                        #endregion

                        #endregion


                        trDML.Commit();
                    }
                    catch (SqlException sqlexep)
                    {
                        trDML.Rollback();
                        ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);

                        ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
                    }
                    catch (Exception exep)
                    {
                        trDML.Rollback();
                        ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);

                        ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
                    }
                    finally
                    {
                        if (Conn.State == ConnectionState.Open)
                        {
                            Conn.Close();
                            Conn.Dispose();
                        }
                    }

                    break;
                   
                }

            case EBS_Common.Classes.InsertUpdateData_Enum.Update:
                {
                    _ObjMaster.Incident_Id = Convert.ToInt32(tbIncident_Id_Hidden.Value);
                    _ObjMaster.Mod_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                    _ObjMaster.UpdateMe(ref grdUploaded_Images, ref grdInc_Images);
                    break;
                }

            case EBS_Common.Classes.InsertUpdateData_Enum.Delete:
                {
                    GetIncident_Img_Path();

                    if (tbDeleted_Remarks.Text != "")
                        _ObjMaster.Deleted_Remarks = tbDeleted_Remarks.Text;
                    else
                        _ObjMaster.Deleted_Remarks = null;

                    _ObjMaster.Incident_Id = Convert.ToInt32(tbIncident_Id_Hidden.Value);
                    _ObjMaster.DeleteMe(DtIncident_Img_Path);
                    break;
                }
        }
        if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", _ObjMaster.ErrorString);
            return;
        }
       
        ClearMe(true);
    }

    protected string Get_Email_Body(String strCallingType)
    {
        String strBody = "";

        strBody = "<tr><td align = " + Convert.ToChar(34) + "left" + Convert.ToChar(34) + "style=" + Convert.ToChar(34) + "font-family: Arial ;font-size: 10pt" + Convert.ToChar(34) + " > Please find the Incident Report attached herewith.</td></tr>";
        strBody += "<tr> <td colspan='2'>&nbsp;</td> </tr>";
        strBody += "<tr> <td colspan='2'>&nbsp;</td> </tr>";
        strBody += "<h3 align='center'>A New Incident has been Recorded";


        strBody += "<table style='font-family: Verdana; font-size: 10pt' width='50%' border='1'> ";
        strBody += "<tr> <td colspan='2'>&nbsp;</td> </tr>";

        strBody += @"<tr><td><b> Incident No.</b></td>
                             <td>" + tbRig_Incident_No.Text + @"</b></td></tr>";

        strBody += @"<tr><td><b> Incident Date/Time  </b></td>
                             <td >" + tbIncident_Date.Text + "  " + tbIncident_Time.Text + @"</b></td></tr>";

        strBody += @"<tr><td><b> Nature of Incident </b></td>
                             <td >" + tbIncident_Type.Text + @"</b></td></tr>";

        strBody += @"<tr><td><b>Rig </b></td>
                             <td >" + tbRig.Text + @"</b></td></tr>";

        strBody += @"<tr><td><b> Well No.</b></td>
                             <td >" + tbWell_No.Text + @"</b></td></tr>";

        strBody += @"<tr><td><b> Reported By</b></td>
                             <td >" + tbReported_By.Text + @"</b></td></tr>";

        strBody += "<tr> <td colspan='2'>&nbsp;</td> </tr>";
        strBody += "</table>";
  
        return strBody;
    }



    protected void btnDelete_Ok_Final_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Delete);
    }

    protected void GetIncident_Img_Path()
    {
        DtIncident_Img_Path.Columns.Clear();
        DtIncident_Img_Path.Rows.Clear();
        
        Conn = new SqlConnection(strConString);

        if (Conn.State == ConnectionState.Closed)
            Conn.Open();

        try
        {
            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Incident_Details", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@Incident_Id", SqlDbType.Int).Value = Convert.ToInt32(tbIncident_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select_Image_Paths";
            Da.Fill(DtIncident_Img_Path);             
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();                
            }
        }
    }
    /// <summary>
    /// To clear the text boxes, default selection of combos.
    /// </summary>
    /// <param name="blnClearMainId">Whether to clear Main Id.</param>
    private void ClearMe(bool blnClearMainId)
    {
        if (blnClearMainId == true)
        {
            tbIncident_Id_Hidden.Value = "";
        }

        tbDeleted_Remarks.Text = "";
        
        tr_Exel_Upload.Visible = true;
        tbWkg_Incident_Dtl_Id_Hidden.Value = "";

        tbRig_Incident_No.Text = "";
        tbRig_Id_Hidden.Value = "";
        tbRig.Text = "";
        tbUnit_Name.Text = "";
 
        tbIncident_Date.Text = "";
        tbIncident_Time.Text = "";
        tbIncident_No.Text = "";

        tbIncident_Reported_Dt.Text = "";
        tbIncident_Reported_Time.Text = "";


        tbCountry_Id_Hidden.Value = "";
        tbCountry_Name.Text = "";
        tbWell_No.Text = "";

        tbOperator_Id_Hidden.Value = "";
        tbOperator_Name.Text = "";

        tbDrilling_Superintendent.Text = "";
        tbSafety_Officer.Text = "";

        tbIncident_Type_Id_Hidden.Value = "";
        tbIncident_Type.Text = "";

        ddlIncident_Severity_Actual.Enabled = true;
        ddlIncident_Severity_Potential.Enabled = true;
        ddlIncident_Severity_Actual.SelectedIndex = 0;
        ddlIncident_Severity_Potential.SelectedIndex = 0;

        ddlPerson_Injured.Enabled = true;

        ibtnPart_Of_Body_Name_1.Enabled = true;
        ibtnPart_Of_Body_Name_2.Enabled = true;
        ibtnPart_Of_Body_Name_3.Enabled = true;
        ibtnPart_Of_Body_Name_4.Enabled = true;

        tbPart_Of_Body_Name_1.Text = "";
        tbPart_Of_Body_Name_2.Text = "";
        tbPart_Of_Body_Name_3.Text = "";
        tbPart_Of_Body_Name_4.Text = "";

        tbPart_Of_Body_Id_Hidden_1.Value  = "";
        tbPart_Of_Body_Id_Hidden_2.Value = "";
        tbPart_Of_Body_Id_Hidden_3.Value = "";
        tbPart_Of_Body_Id_Hidden_4.Value = "";

        tbDMS_Path_QHSE.Text = "";
        tbDMS_Folder_Name.Text = "";
        tbResume_File_Name.Text = "";

        ddlPerson_Injured.SelectedValue = "Y";
        ddlThird_Party.Enabled = true;
        ddlThird_Party.SelectedValue = "";

        ddlIncident_Party.Enabled = true;
        ddlIncident_Party.SelectedValue = "";

        tbContractor_Id_Hidden.Value = "";
        tbContractor_Name.Text = "";


        tbEmp_Name.Text = "";
        tbRank_Id_Hidden.Value = "";
        tbRank_Name.Text = "";
        tbTotal_Rig_Exp_Months.Text = "";
        tbImmediate_Cause_Descr.Text = "";
        tbIncident_Descr.Text = "";

        tbImmediate_Cause_1.Text = "";
        tbImmediate_Incident_Cause_Id_1_Hidden.Value = "";

        tbImmediate_Cause_2.Text = "";
        tbImmediate_Incident_Cause_Id_2_Hidden.Value = "";


        tbRig_Operation_Id_Hidden.Value = "";
        tbRig_Operation_Name.Text = "";

        tbWork_Location_Id_Hidden.Value = "";
        tbWork_Location_Name.Text = "";

        tbContact_Expo_Type_Id_Hidden.Value = "";
        tbContact_Expo_Type_Name.Text = "";

        tbCorrective_Action.Text = "";
        tbPreventive_Action.Text = "";

        tbFinancial_Loss_Currency_Id_Hidden.Value = "";
        tbMaxExchangeRate_Hidden.Value = "";


        tbNPT_Hrs_Loss.Text = "";
        tbManhours_Loss.Text = "";
        tbExchange_Rate.Text = "";
        tbFinancial_Loss_Amt.Text = "";
        tbFinancial_Loss_BC_Amt.Text = "";
        tbFinancial_Loss_Currency.Text = "";

        ///Reported by 
        tbReported_By.Text = "";
        tbRptd_By_Rank_Name.Text = "";
        tbFs_Emp_Id_Hidden.Value = "";

        tbComments.Text = "";
        grdInc_Images.DataSource = null;
        grdInc_Images.DataBind();

        grdUploaded_Images.DataSource = null;
        grdUploaded_Images.DataBind();

        #region To enable controls and change the css


        tbRig_Incident_No.CssClass = "textbox";
        tbUnit_Name.CssClass = "textbox";
        tbIncident_Date.CssClass = "textbox";
        tbIncident_Time.CssClass = "textbox";
        tbWell_No.CssClass = "textbox";
        tbDrilling_Superintendent.CssClass = "textbox";
        tbSafety_Officer.CssClass = "textbox";
        tbEmp_Name.CssClass = "textbox";
        tbTotal_Rig_Exp_Months.CssClass = "textbox_right";
        tbIncident_Descr.CssClass = "textbox";
        tbImmediate_Cause_Descr.CssClass = "textbox";
        tbCorrective_Action.CssClass = "textbox";
        tbPreventive_Action.CssClass = "textbox";
        tbComments.CssClass = "textbox";

        tbNPT_Hrs_Loss.CssClass = "textbox_right";
        tbManhours_Loss.CssClass = "textbox_right";
        tbFinancial_Loss_Amt.CssClass = "textbox_right";

        //tbFinancial_Loss_BC_Amt.CssClass = "textbox_right_readonly";
        //tbExchange_Rate.CssClass = "textbox_right_readonly";


        tbIncident_Reported_Dt.CssClass = "textbox";
        tbIncident_Reported_Time.CssClass = "textbox";

        tbRig_Incident_No.Attributes.Remove("OnKeyDown");
        tbUnit_Name.Attributes.Remove("OnKeyDown");
        tbIncident_Date.Attributes.Remove("OnKeyDown");
        tbIncident_Time.Attributes.Remove("OnKeyDown");
        tbWell_No.Attributes.Remove("OnKeyDown");
        tbDrilling_Superintendent.Attributes.Remove("OnKeyDown");
        tbSafety_Officer.Attributes.Remove("OnKeyDown");
        tbEmp_Name.Attributes.Remove("OnKeyDown");
        tbTotal_Rig_Exp_Months.Attributes.Remove("OnKeyDown");
        tbIncident_Descr.Attributes.Remove("OnKeyDown");
        tbImmediate_Cause_Descr.Attributes.Remove("OnKeyDown");
        tbCorrective_Action.Attributes.Remove("OnKeyDown");
        tbPreventive_Action.Attributes.Remove("OnKeyDown");
        tbComments.Attributes.Remove("OnKeyDown");
        tbIncident_Reported_Dt.Attributes.Remove("OnKeyDown");
        tbIncident_Reported_Time.Attributes.Remove("OnKeyDown");
        tbNPT_Hrs_Loss.Attributes.Remove("OnKeyDown");
        tbManhours_Loss.Attributes.Remove("OnKeyDown");
        tbFinancial_Loss_Amt.Attributes.Remove("OnKeyDown");
        #endregion

        #region Buttons
        ibtnRig.Visible = true;
        ibtnCountry.Visible = true;
        ibtntbOperator.Visible = true;
        ibtnIncident_Type.Visible = true;
        ibtnContractor.Visible = true;
        ibtnRank.Visible = true;
        ibtnImmediate_Incident_Cause_1.Visible = true;
        ibtnImmediate_Incident_Cause_2.Visible = true;
        ibtnRig_Opeartion.Visible = true;
        ibtnWork_Location.Visible = true;
        ibtntbContact_Expo_Type.Visible = true;
        ibtnFinancial_Loss_Currency_Id.Visible = true;
        ibtnRptd_By_Rank_Name.Visible = true;
        ibtnFs_Emp_Name.Visible = true;
        ibtnRig.Visible = true;
        #endregion
        Bind_Images_File_Upload();
        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Clear");
    }

    protected void btnAdd_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Insert);
    }

    protected void Get_Data_For_Edit()
    {
        ClearMe(false);
        Conn = new SqlConnection(strConString);
        try
        {

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Incident_Details", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@Incident_Id", SqlDbType.Int).Value = Convert.ToInt32(tbIncident_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select";
            Da.Fill(Ds, "Data_For_Edit");


            tbRig_Incident_No.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Incident_No"].ToString();
            tbRig_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Id"].ToString();

            tbRig.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Name"].ToString();
            tbUnit_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Unit_Name"].ToString();

            tbIncident_Date.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Date"].ToString();
            tbIncident_Time.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Time"].ToString();
            tbIncident_No.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_No"].ToString();

            tbIncident_Reported_Dt.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Reported_Dt"].ToString();
            tbIncident_Reported_Time.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Reported_Time"].ToString();

            ddlPerson_Injured.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Person_Injured"].ToString();      
            
            
            tbPart_Of_Body_Name_1.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Part_Of_Body_Name_1"].ToString();
            tbPart_Of_Body_Id_Hidden_1.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Part_Of_Body_Id_1"].ToString();

            
            tbPart_Of_Body_Name_2.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Part_Of_Body_Name_2"].ToString();
            tbPart_Of_Body_Id_Hidden_2.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Part_Of_Body_Id_2"].ToString();

            
            tbPart_Of_Body_Name_3.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Part_Of_Body_Name_3"].ToString();
            tbPart_Of_Body_Id_Hidden_3.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Part_Of_Body_Id_3"].ToString();

            
            tbPart_Of_Body_Name_4.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Part_Of_Body_Name_4"].ToString();
            tbPart_Of_Body_Id_Hidden_4.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Part_Of_Body_Id_4"].ToString();

            string setRegisterStartUpScript = "";
            if (ddlPerson_Injured.SelectedValue != "Y")
            {
                setRegisterStartUpScript = "ShowHideBodyParts('N');";
            }
            else
            {
                setRegisterStartUpScript = "ShowHideBodyParts('Y');";
            }

            tbCountry_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Country_Id"].ToString();
            tbCountry_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Country_Name"].ToString();
            tbWell_No.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Well_No"].ToString();

            tbOperator_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Operator_Id"].ToString();
            tbOperator_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Operator_Name"].ToString();

            tbDrilling_Superintendent.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Drilling_Superintendent"].ToString();
            tbSafety_Officer.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Safety_Officer"].ToString();

            tbIncident_Type_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Type_Id"].ToString();
            tbIncident_Type.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Type"].ToString();

            ddlIncident_Severity_Actual.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Severity_Actual"].ToString();
            ddlIncident_Severity_Potential.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Severity_Potential"].ToString();


            ddlIncident_Party.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Party"].ToString();
            ddlThird_Party.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Third_Party"].ToString();

            tbContractor_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Contractor_Id"].ToString();
            tbContractor_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Contractor_Name"].ToString();

            tbEmp_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Emp_Name"].ToString();

            tbRank_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Rank_Id"].ToString();
            tbRank_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Rank_Name"].ToString();
            tbTotal_Rig_Exp_Months.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Total_Rig_Exp_Months"].ToString();

            tbIncident_Descr.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Incident_Descr"].ToString();

            tbImmediate_Cause_Descr.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Immediate_Cause_Descr"].ToString();

            tbImmediate_Cause_1.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Immediate_Cause_1"].ToString();
            tbImmediate_Incident_Cause_Id_1_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Immediate_Incident_Cause_Id_1"].ToString();

            tbImmediate_Cause_2.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Immediate_Cause_2"].ToString();
            tbImmediate_Incident_Cause_Id_2_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Immediate_Incident_Cause_Id_2"].ToString();


            tbRig_Operation_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Operation_Id"].ToString();
            tbRig_Operation_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Operation_Name"].ToString();

            tbWork_Location_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Work_Location_Id"].ToString();
            tbWork_Location_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Work_Location_Name"].ToString();

            tbContact_Expo_Type_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Contact_Expo_Type_Id"].ToString();
            tbContact_Expo_Type_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Contact_Expo_Type_Name"].ToString();

            tbCorrective_Action.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Corrective_Action"].ToString();
            tbPreventive_Action.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Preventive_Action"].ToString();

            tbFinancial_Loss_Currency_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Financial_Loss_Currency_Id"].ToString();



            tbNPT_Hrs_Loss.Text = Ds.Tables["Data_For_Edit"].Rows[0]["NPT_Hrs_Loss"].ToString();
            tbManhours_Loss.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Manhours_Loss"].ToString();
            tbExchange_Rate.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Exchange_Rate"].ToString();
            tbFinancial_Loss_Amt.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Financial_Loss_Amt"].ToString();
            tbFinancial_Loss_BC_Amt.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Financial_Loss_BC_Amt"].ToString();
            tbFinancial_Loss_Currency.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Financial_Loss_Currency"].ToString();

            ///Reported by 
            tbReported_By.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Reported_By"].ToString();
            tbRptd_By_Rank_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Rptd_By_Rank_Name"].ToString();
            tbRptd_By_Rank_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Rptd_By_Rank_Id"].ToString();

            tbFs_Emp_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Fs_Emp_Id"].ToString();

            tbComments.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Comments"].ToString();
            //Bind the uploaded images to the Grid.
            grdUploaded_Images.DataSource = Ds.Tables["Data_For_Edit1"];
            grdUploaded_Images.DataBind();

            //sumit Dms path
            #region DMS path
            string strDMS_Path_QHSE = Ds.Tables["Data_For_Edit"].Rows[0]["DMS_Path_QHSE"].ToString();

            string strFileName = "", strFinal_DMS_Path = "";
            if (strDMS_Path_QHSE != "")
            {

                if (strDMS_Path_QHSE.Contains("*"))///* means Folder Name is not Entered
                {
                    tbDMS_Path_QHSE.Text = strDMS_Path_QHSE.Substring(0, strDMS_Path_QHSE.LastIndexOf('*'));
                    tbDMS_Folder_Name.Text = "";
                    tbResume_File_Name.Text = strDMS_Path_QHSE.Substring(strDMS_Path_QHSE.LastIndexOf('*') + 1, strDMS_Path_QHSE.Length - strDMS_Path_QHSE.LastIndexOf('*') - 1);
                }
                else
                {
                    if (strDebugModeYN == "Y")
                    {
                        tbDMS_Path_QHSE.Text = "http://essdmsmum/espl/ShippingPortLogistics/IT/System/";
                    }
                    else
                    {
                        if (tbDMS_Path_QHSE.Text == "")
                        {
                            tbDMS_Path_QHSE.Text = "http://Essdmsmum/espl/Oilfieldservices/QHSE Documents/";
                        }
                    }
                    strFileName = strDMS_Path_QHSE.Substring(strDMS_Path_QHSE.LastIndexOf('/') + 1, strDMS_Path_QHSE.Length - strDMS_Path_QHSE.LastIndexOf('/') - 1);
                    tbDMS_Folder_Name.Text = strDMS_Path_QHSE.Substring(tbDMS_Path_QHSE.Text.Length).Substring(0, strDMS_Path_QHSE.Substring(tbDMS_Path_QHSE.Text.Length).IndexOf(strFileName));
                    tbResume_File_Name.Text = strFileName;


                    //if (strDMS_Path_QHSE.Length > strDMS_Path_QHSE.LastIndexOf('/') + 1)
                    //{
                    //    int intLastDash = strDMS_Path_QHSE.LastIndexOf('/') + 1;
                    //    //StartIndex - LastIndexOf('/') and EndIndex (Total resume Path Length - )
                    //    strFileName = strDMS_Path_QHSE.Substring(strDMS_Path_QHSE.LastIndexOf('/') + 1, strDMS_Path_QHSE.Length - strDMS_Path_QHSE.LastIndexOf('/') - 1);

                    //    strFinal_DMS_Path = strDMS_Path_QHSE.Substring(0, strDMS_Path_QHSE.LastIndexOf('/'));

                    //    int intSecondLastDash = 0;

                    //    if (strFinal_DMS_Path.Length > strFinal_DMS_Path.LastIndexOf('/') + 1)
                    //    {
                    //        intSecondLastDash = strFinal_DMS_Path.LastIndexOf('/') + 1;

                    //        strFinal_DMS_Path = strDMS_Path_QHSE.Substring(0, strFinal_DMS_Path.LastIndexOf('/') + 1);
                    //    }

                    //    tbDMS_Path_QHSE.Text = strFinal_DMS_Path;
                    //    tbDMS_Folder_Name.Text = strDMS_Path_QHSE.Substring(intSecondLastDash, intLastDash - intSecondLastDash);
                    //    tbResume_File_Name.Text = strFileName;
                    //}
                    //else
                    //{
                    //    tbDMS_Path_QHSE.Text = strDMS_Path_QHSE;
                    //    tbDMS_Folder_Name.Text = "";
                    //    tbResume_File_Name.Text = "";
                    //}
                }
            }
            else
            {
                tbDMS_Path_QHSE.Text = strDMS_Path_QHSE;
                tbDMS_Folder_Name.Text = "";
                tbResume_File_Name.Text = "";
            }


            #endregion



            ///If Incident status is closed then all fields must be displayed only and cannot be updated. 

            ibtnRig.Visible = false;
            ibtnCountry.Visible = false;
            setRegisterStartUpScript += "document.getElementById('imgCountry_Name').style.display = 'none';";
            ///ibtntbOperator.Visible = false;
            //setRegisterStartUpScript += "document.getElementById('imgOperator_Name').style.display = 'none';";
            ibtnIncident_Type.Visible = false;
            //ibtnContractor.Visible = false;
            //ibtnRank.Visible = false;
            ibtnImmediate_Incident_Cause_1.Visible = false;
            ibtnImmediate_Incident_Cause_2.Visible = false;

            setRegisterStartUpScript += "document.getElementById('imgImmediate_Incident_Cause_2').style.display = 'none';";
            
            ibtnRig_Opeartion.Visible = false;
            ibtnWork_Location.Visible = false;
            ibtntbContact_Expo_Type.Visible = false;

            tr_Exel_Upload.Visible = false;

            
            tbUnit_Name.Attributes.Add("OnKeyDown", "return RejectInput()");
            tbIncident_Date.Attributes.Add("OnKeyDown", "return RejectInput()");
            tbIncident_Time.Attributes.Add("OnKeyDown", "return RejectInput()");
            //tbWell_No.Attributes.Add("OnKeyDown", "return RejectInput()");
            tbDrilling_Superintendent.Attributes.Add("OnKeyDown", "return RejectInput()");
            tbSafety_Officer.Attributes.Add("OnKeyDown", "return RejectInput()");
            //tbEmp_Name.Attributes.Add("OnKeyDown", "return RejectInput()");
            //tbTotal_Rig_Exp_Months.Attributes.Add("OnKeyDown", "return RejectInput()");





            tbIncident_Reported_Dt.Attributes.Add("OnKeyDown", "return RejectInput()");
            tbIncident_Reported_Time.Attributes.Add("OnKeyDown", "return RejectInput()");

            
            tbUnit_Name.CssClass = "textbox_readonly";
            tbIncident_Date.CssClass = "textbox_readonly";
            tbIncident_Time.CssClass = "textbox_readonly";
            //tbWell_No.CssClass = "textbox_readonly";
            tbDrilling_Superintendent.CssClass = "textbox_readonly";
            tbSafety_Officer.CssClass = "textbox_readonly";
            //tbEmp_Name.CssClass = "textbox_readonly";
            //tbTotal_Rig_Exp_Months.CssClass = "textbox_right_readonly";

            tbIncident_Reported_Dt.CssClass = "textbox_readonly";
            tbIncident_Reported_Time.CssClass = "textbox_readonly";
            //ddlIncident_Severity_Actual.Enabled = false;
            //ddlIncident_Severity_Potential.Enabled = false;
            //ddlPerson_Injured.Enabled = false;
            //ddlThird_Party.Enabled = false;

            Page.RegisterStartupScript("starScript", "<script language=JavaScript>" + setRegisterStartUpScript  + "</script>");

        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }

        }
    }

    protected void Get_Wkg_Incident_Dtl(ref SqlConnection Conn, ref SqlTransaction trDML)
    {
        try
        {

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Wkg_Incident_Dtl", Conn);
            Da.SelectCommand.Transaction = trDML;
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;


            Da.SelectCommand.Parameters.Add("@Wkg_Incident_Id", SqlDbType.Int).Value = Convert.ToInt32(tbWkg_Incident_Dtl_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Del_Cur_Wkg_Record", SqlDbType.VarChar).Value = "Y";
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select";
            Da.Fill(Ds, "Wkg_Incident_Dtl_Data");


            tbRig_Incident_No.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rig_Incident_No"].ToString();
            tbRig_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rig_Id"].ToString();

            tbRig.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rig_Name"].ToString();
            tbUnit_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Unit_Name"].ToString();

            tbIncident_Date.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Date"].ToString();
            tbIncident_Time.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Time"].ToString();
            /*as this Fields are not in Working Table so set them as NULL from database*/
            tbIncident_No.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_No"].ToString();

            tbIncident_Reported_Dt.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Reported_Dt"].ToString();
            tbIncident_Reported_Time.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Reported_Time"].ToString();

            ddlPerson_Injured.SelectedValue = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Person_Injured"].ToString();

            tbPart_Of_Body_Name_1.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Part_Of_Body_Name_1"].ToString();
            tbPart_Of_Body_Name_2.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Part_Of_Body_Name_2"].ToString();
            tbPart_Of_Body_Name_3.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Part_Of_Body_Name_3"].ToString();
            tbPart_Of_Body_Name_4.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Part_Of_Body_Name_4"].ToString();

            tbPart_Of_Body_Id_Hidden_1.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Part_Of_Body_Id_1"].ToString();
            tbPart_Of_Body_Id_Hidden_2.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Part_Of_Body_Id_2"].ToString();
            tbPart_Of_Body_Id_Hidden_3.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Part_Of_Body_Id_3"].ToString();
            tbPart_Of_Body_Id_Hidden_4.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Part_Of_Body_Id_4"].ToString();

            tbCountry_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Country_Id"].ToString();
            tbCountry_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Country_Name"].ToString();
            tbWell_No.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Well_No"].ToString();

            tbOperator_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Operator_Id"].ToString();
            tbOperator_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Operator_Name"].ToString();

            tbDrilling_Superintendent.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Drilling_Superintendent"].ToString();
            tbSafety_Officer.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Safety_Officer"].ToString();

            tbIncident_Type_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Type_Id"].ToString();
            tbIncident_Type.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Type"].ToString();

            ddlIncident_Severity_Actual.SelectedValue = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Severity_Actual"].ToString();
            ddlIncident_Severity_Potential.SelectedValue = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Severity_Potential"].ToString();

            ddlThird_Party.SelectedValue = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Third_Party"].ToString();
            ddlIncident_Party.SelectedValue = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Party"].ToString();

            tbContractor_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Contractor_Id"].ToString();
            tbContractor_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Contractor_Name"].ToString();
            /*as this Fields are not in Working Table so set them as NULL from database*/
            tbEmp_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Emp_Name"].ToString();


            tbRank_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rank_Id"].ToString();
            tbRank_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rank_Name"].ToString();
            tbTotal_Rig_Exp_Months.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Total_Rig_Exp_Months"].ToString();

            tbIncident_Descr.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Incident_Descr"].ToString();

            tbImmediate_Cause_Descr.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Immediate_Cause_Descr"].ToString();

            tbImmediate_Cause_1.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Immediate_Cause_1"].ToString();
            tbImmediate_Incident_Cause_Id_1_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Immediate_Incident_Cause_Id_1"].ToString();

            tbImmediate_Cause_2.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Immediate_Cause_2"].ToString();
            tbImmediate_Incident_Cause_Id_2_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Immediate_Incident_Cause_Id_2"].ToString();


            tbRig_Operation_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rig_Operation_Id"].ToString();
            tbRig_Operation_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rig_Operation_Name"].ToString();

            tbWork_Location_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Work_Location_Id"].ToString();
            tbWork_Location_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Work_Location_Name"].ToString();

            tbContact_Expo_Type_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Contact_Expo_Type_Id"].ToString();
            tbContact_Expo_Type_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Contact_Expo_Type_Name"].ToString();


            tbCorrective_Action.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Corrective_Action"].ToString();
            tbPreventive_Action.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Preventive_Action"].ToString();

            /*as this Fields are not in Working Table so set them as NULL from database*/
            tbFinancial_Loss_Currency_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Financial_Loss_Currency_Id"].ToString();

            tbNPT_Hrs_Loss.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["NPT_Hrs_Loss"].ToString();
            tbManhours_Loss.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Manhours_Loss"].ToString();

            /*as this Fields are not in Working Table so set them as NULL from database*/
            tbExchange_Rate.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Exchange_Rate"].ToString();
            tbFinancial_Loss_Amt.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Financial_Loss_Amt"].ToString();

            /*as this Fields are not in Working Table so set them as NULL from database*/
            tbFinancial_Loss_BC_Amt.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Financial_Loss_BC_Amt"].ToString();
            tbFinancial_Loss_Currency.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Financial_Loss_Currency"].ToString();

            ///Reported by 
            tbReported_By.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Reported_By"].ToString();
            tbRptd_By_Rank_Name.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rptd_By_Rank_Name"].ToString();
            tbRptd_By_Rank_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Rptd_By_Rank_Id"].ToString();

            /*as this Fields are not in Working Table so set them as NULL from database*/
            tbFs_Emp_Id_Hidden.Value = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Fs_Emp_Id"].ToString();

            tbComments.Text = Ds.Tables["Wkg_Incident_Dtl_Data"].Rows[0]["Comments"].ToString();
            //Set_Max_Incident_No();
            string strstartscript="";
            if (ddlPerson_Injured.SelectedValue == "N") {
                strstartscript = "Disp_Person_Injured();";
            }
            Page.RegisterStartupScript("starScript", "<script language=JavaScript>" + strstartscript + "</script>");
        }

        catch (SqlException sqlexep)
        {
            ErrorString = sqlexep.Message;
            return;
        }
        catch (Exception exep)
        {
            ErrorString = exep.Message;
            return;
        }

    }

   
    protected void btnClear_Click(object sender, EventArgs e)
    {
        ClearMe(true);
    }

    protected void btnUpdate_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Update);
    }

    ///As temporary removed this Portion as Currency data is not updated in the Master 09 July 2013
    ///Also removed the JAVASCRIPT event  onKeyUp="Validate_Financial_Loss_Amt();"

    //protected void tbFinancial_Loss_Amt_TextChanged(object sender, EventArgs e)
    //{
    //    CalculateBaseCurrency();
    //}

    protected void CalculateBaseCurrency()
    {

        if (tbFinancial_Loss_Currency_Id_Hidden.Value == "")
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", "alert('Select Currency first.');", true);
            tbFinancial_Loss_Amt.Text = "";
            return;
        }
        if (tbIncident_Date.Text == "")
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", "alert('Enter Incident Date first.');", true);
            tbFinancial_Loss_Amt.Text = "";
            return;
        }
        decimal decExchRt = 0;
        string strExchangeRateDt = "";
        decExchRt = GetExchangeRate(Convert.ToByte(tbFinancial_Loss_Currency_Id_Hidden.Value), tbIncident_Date.Text, false, ref strExchangeRateDt);
        tbMaxExchangeRate_Hidden.Value = "";

        if (decExchRt == 0)
        {
            #region Commented: Not to allow to proceed if exch. rate not entered by 12 pm
            /*
            if (DateTime.Now.Hour >= 12)
            {
                tbExchange_Rate.Text = "";
                tbFinancial_Loss_BC_Amt.Text = "";
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", "alert('No Exchange Rate Found in Exchange Rate Master. Kindly enter Exchange Rate.');", true);
                return;
            }
            */
            #endregion

            decExchRt = GetExchangeRate(Convert.ToByte(tbFinancial_Loss_Currency_Id_Hidden.Value), tbIncident_Date.Text, true, ref strExchangeRateDt);
            tbMaxExchangeRate_Hidden.Value = decExchRt.ToString();
        }
        tbExchange_Rate.Text = decExchRt.ToString();
        try
        {
            tbFinancial_Loss_BC_Amt.Text = Convert.ToString(Convert.ToInt32(decExchRt * Convert.ToDecimal(tbFinancial_Loss_Amt.Text)));
        }
        catch (Exception exep)
        {
            tbFinancial_Loss_BC_Amt.Text = "0";
        }
    }

    protected decimal GetExchangeRate(byte intCurrency_Id, string dtExchange_Rate, bool blnGetLastExchRate, ref string strExchRateDt)
    {
        #region Local Variables
        decimal decExchange_Rate = 0;
        string strSql = "";
        #endregion

        #region Calculating Base Currency Amt
        if (intCurrency_Id == 1) // INR then ignore
        {
            decExchange_Rate = 1;
        }
        else
        {
            Conn = new SqlConnection(strConString);
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();
            if (blnGetLastExchRate)
            {
                strSql = @"Select Convert(Char(10), Exchange_Rate_From,103) Exchange_Rate_From_Dt, Exchange_Rate From " + OI.Glo + @"Exchange_Rate_Mst Where Currency_Id = @Currency_Id 
                and Exchange_Rate_Freq ='D' 
                and Exchange_Rate_From In 
                (Select MAX(Exchange_Rate_From) 
                From " + OI.Glo + @"Exchange_Rate_Mst 
                Where Currency_Id = @Currency_Id
                and Exchange_Rate_Freq ='D' )";
            }
            else
            {
                strSql = "Select Convert(Char(10), Exchange_Rate_From,103) Exchange_Rate_From_Dt, Exchange_Rate From " + OI.Glo + @"Exchange_Rate_Mst Where Currency_Id = @Currency_Id and ( @Exchange_Rate_Dt >= Exchange_Rate_From and @Exchange_Rate_Dt <= Exchange_Rate_To ) and Exchange_Rate_Freq ='D' ";
            }

            Ds = new DataSet();
            Da = new SqlDataAdapter(strSql, Conn);

            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.Parameters.Add("Currency_Id", System.Data.SqlDbType.TinyInt).Value = intCurrency_Id;
            if (blnGetLastExchRate == false)
                Da.SelectCommand.Parameters.Add("Exchange_Rate_Dt", System.Data.SqlDbType.Date).Value = Convert.ToDateTime(DateTime.ParseExact(dtExchange_Rate, "dd/MM/yyyy", null));

            Da.Fill(Ds, "ExchangeRate");
            if (Ds.Tables["ExchangeRate"].Rows.Count > 0)
            {
                try
                {
                    decExchange_Rate = Convert.ToDecimal(Ds.Tables["ExchangeRate"].Rows[0]["Exchange_Rate"]);
                }
                catch
                {
                    decExchange_Rate = 0;
                }
                strExchRateDt = Ds.Tables["ExchangeRate"].Rows[0]["Exchange_Rate_From_Dt"].ToString();
            }
        }

        return decExchange_Rate;
        #endregion
    }


//    protected void Set_Max_Incident_No()
//    {

//        if (tbRig_Id_Hidden.Value.ToString() == "")
//        {
//            tbIncident_No.Text = "1";///For the unit Insert 
//            return;
//        }

//        Conn = new SqlConnection(strConString);
//        try
//        {

//            strSql = @" Select isnull(max(Incident_No),0) + 1 [Incident_No]  From " + OI.Def + @"Incident_Details
//                       Where 
//                       Rig_Id = @Rig_Id And 
//                       Financial_Year_Id = " + OI.Glo + @"Fnc_Get_Fin_Yr_Id(@Incident_Date) ";

//            if (Conn.State == ConnectionState.Closed)
//                Conn.Open();

//            Ds = new DataSet();
//            Da = new SqlDataAdapter(strSql, Conn);
//            Da.SelectCommand.Parameters.Add("@Rig_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbRig_Id_Hidden.Value);
//            Da.SelectCommand.Parameters.Add("@Incident_Date", SqlDbType.Date).Value = Convert.ToDateTime(DateTime.ParseExact(tbIncident_Date.Text, "dd/MM/yyyy", null));

//            Da.Fill(Ds, "DataForIncidentNo");

//            tbIncident_No.Text = Ds.Tables["DataForIncidentNo"].Rows[0]["Incident_No"].ToString();

//        }
//        catch (SqlException sqlexep)
//        {
//            tbIncident_No.Text = "";
//            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
//            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
//            return;
//        }
//        catch (Exception exep)
//        {
//            tbIncident_No.Text = "";
//            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
//            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
//            return;
//        }
//        finally
//        {
//            if (Conn.State == ConnectionState.Open)
//            {
//                Conn.Close();
//            }
//        }
//    }


    protected void GetCountry_Well()
    {

        if (tbRig_Id_Hidden.Value.ToString() == "")
        {
            return;
        }

        Conn = new SqlConnection(strConString);
        try
        {
            ///h.Location  is the Well No IN THIS CASE.
            strSql = @" Select h.Location 
                        From " + OI.Def + @"Drilling_Hdr h, " + OI.Def + @"Drilling_Dtl d
                        where h.Rig_Id = @Rig_Id and d.Drilling_Dtl_Dt = @Drilling_Dtl_Dt
                            and h.Drilling_Hdr_Id = d.Drilling_Hdr_Id";

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(strSql, Conn);
            Da.SelectCommand.Parameters.Add("@Rig_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbRig_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Drilling_Dtl_Dt", SqlDbType.Date).Value = Convert.ToDateTime(DateTime.ParseExact(tbIncident_Date.Text, "dd/MM/yyyy", null));

            Da.Fill(Ds, "DataForCountry_Well");

            if (Ds.Tables["DataForCountry_Well"].Rows.Count > 0)
                tbWell_No.Text = Ds.Tables["DataForCountry_Well"].Rows[0]["Location"].ToString();
            else
                tbWell_No.Text = "";

            tbIncident_Time.Focus();
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
            }

        }
    }

    private string Call_Report(string strCaller, ref SqlTransaction trDML, ref SqlConnection Conn)
    {
        string ErrorString = "";

        string strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();
        //SqlConnection Conn = new SqlConnection(strConString);
        string strFile_Path = "";
        string[] strarrParams = new string[1];

        strarrParams[0] = clsSystem_Generic_Info.Report_Dt_Caption.ToString();
        try
        {
            string strAuth_Sign_Photo_URL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();

            string strReport_File_Path = Server.MapPath("~/Reports/Accident_Incident_Report.rpt");
             
     
            string strTemp_File_Path = Server.MapPath("~/TempReports");
            string PFile = "";

            if (strCaller == "Print")
            {
                PFile = "Incident_Report_" +  Session.SessionID.ToString() + "_" + DateTime.Now.ToString("mm") + DateTime.Now.ToString("ss") + DateTime.Now.ToString("ff") + "_Prn.pdf";
            }
            else
            {
                PFile = "Incident_Report_" +  Session.SessionID.ToString() + "_" + DateTime.Now.ToString("mm") + DateTime.Now.ToString("ss") + DateTime.Now.ToString("ff") + ".pdf";
            }

            string strTemp_File_Name = PFile;
            strFile_Path = strTemp_File_Path + "\\" + strTemp_File_Name; 

            clsrIncident_Report _Obj = new clsrIncident_Report();
             
            #region These 2 dates are imporatant to decide which header footer to dispay New / Old company
            _Obj.Effective_Date = tbIncident_Date.Text;
            _Obj.Prj_Cutoff_Date = ConfigurationManager.ConnectionStrings["Prj_Cutoff_Date"].ToString();
            #endregion
            
            byte bytReturn = _Obj.Get_Fs_Emp_Contract_Details(ref trDML,ref Conn, strReport_File_Path, PFile, strTemp_File_Path, strarrParams, Convert.ToInt32(tbIncident_Id_Hidden.Value),  strAuth_Sign_Photo_URL );

            if (bytReturn == 1)
            {
                if (strCaller == "Print")
                {
                    HttpContext.Current.Response.Clear();
                    HttpContext.Current.Response.ClearHeaders();

                    HttpContext.Current.Response.ContentType = "application/pdf";

                    HttpContext.Current.Response.AppendHeader("Content-Disposition", "attachment; filename=" + strTemp_File_Name + " ");
                    HttpContext.Current.Response.TransmitFile(strFile_Path);
                    HttpContext.Current.Response.Flush();
                    HttpContext.Current.Response.End();
                }
            }
            else
            {
                //ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", "alert('No Data for this criterion')", true);
                strFile_Path = "";
                throw new Exception("Err:No Data for this criterion");

            }
             

            return strFile_Path;

        }
        catch (SqlException sqlexep)
        {
            return "Err:" + sqlexep.Message.ToString();
        }
        catch (Exception exep)
        {

            return "Err:" + exep.Message.ToString();
        }
        finally
        {
            //if (Conn.State == ConnectionState.Open)
            //{
            //    Conn.Close();
            //}
        }
    }



    protected void btnPrint_Click(object sender, EventArgs e)
    {
        Conn = new SqlConnection(strConString);
        SqlTransaction trDML;

        if (Conn.State == ConnectionState.Closed)
            Conn.Open();

        trDML = Conn.BeginTransaction();

        try
        {
            string strRes = Call_Report("Print", ref trDML, ref Conn);

            if (strRes.Contains("Err:"))
            {
                throw new Exception(strRes.Replace("Err:", ""));
            }
        }

        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            trDML.Rollback();
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            trDML.Rollback();
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }
        }
    }


    #region
    //    protected void btnPrint_Click1(object sender, EventArgs e)
//    {

          

//        #region Variable & Object Declaration
//        string strQuery = "";
//        string ErrorString = "";
//        Conn = new SqlConnection(strConString);
//        DataSet Ds = new DataSet();
//        #endregion

//        try
//        {
//            #region Report Query: Accident Incident Report , And Photo Path

//            strQuery = @"Select 
//				                        Incident_Id,
//				                        case when Rig_Id IS NULL then unit_name
//				                        else " + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Rig', Rig_Id,'NAME') 
//				                        end as [Rig_Unit],Rig_Incident_No,
//				                        CONVERT(varchar(10), Incident_Date, 103) + ' ' + Convert(Varchar(5), Incident_Date, 108) [Incident_Date_Time],
//				                        CONVERT(varchar(10), Incident_Reported_Dt, 103) + ' ' + Convert(Varchar(5), Incident_Reported_Dt, 108) [Incident_Reported_Date_Time], Well_No,                      
//				                        " + OI.Glo + @"Fnc_Get_Col_Value('" + OI.Glo + @"Mst_Country', Country_Id, 'NAME') [Country],
//				                        " + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Operator',Operator_Id,'NAME') as Operator_Name, 
//
//				                        " + OI.Glo + @"Fnc_Get_Col_Value('" + OI.Glo + @"Mstx_Incident_Type',Incident_Type_Id,'NAME') [Nature_of_Incident],
//				                        " + OI.Glo + @"Fnc_Get_Col_Result('Incident_Severity_Potential',Incident_Severity )[Incident_Severity_Actual],
//				                        " + OI.Glo + @"Fnc_Get_Col_Result('Incident_Severity_Potential',Incident_Severity_Potential)Incident_Severity_Potential,
//
//				                        /*Start -- Person_Injured*/
//				                        Person_Injured,
//				                        case when  Third_Party ='N' then 'EOSIL'			                        
//				                        when  Third_Party ='Y' then " + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Contractor',Contractor_Id,'NAME')
//				                        
//				                        else '' end as 
//				                        
//				                        [Third_Party_Belongs_To] ," + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Contractor',Contractor_Id,'NAME') as Contractor_Name,
//				                        Emp_Name,
//				                        case when RANK_Id IS NULL then Rank_Name 
//				                        else DBO.Fnc_Get_Col_Value('DBO.Mst_Rank', Rank_Id,'NAME') 
//				                        end as [Rank_Name] ,Total_Rig_Exp_Months,
//				                        /*End -- Person_Injured*/
//
//
//				                        Incident_Descr,
//
//				                        /*Start -- Probable causes of Occurrence*/
//				                        '1) ' + " + OI.Glo + @"Fnc_Get_Col_Value('" + OI.Glo + @"Mstx_Incident_Cause',Immediate_Incident_Cause_Id,'NAME') [Immediate_Incident_Cause_Id_1],                                
//				                        '2) ' + " + OI.Glo + @"Fnc_Get_Col_Value('" + OI.Glo + @"Mstx_Incident_Cause',Immediate_Incident_Cause_Id_2,'NAME')  Immediate_Incident_Cause_Id_2 ,
//				                        Immediate_Cause_Descr,
//				                        /*End -- Probable causes of Occurrence*/
//
//
//				                        eos.Fnc_Get_Col_Value('eos.Mst_Rig_Operation',Rig_Operation_Id,'NAME') as Rig_Operation_Name, 
//				                        dbo.Fnc_Get_Col_Value('dbo.Mstx_Work_Location',Work_Location_Id,'NAME') as Work_Location_Name ,
//				                        eos.Fnc_Get_Col_Value('eos.Mst_Contact_Exposure_Type',Contact_Expo_Type_Id,'NAME') as Contact_Expo_Type_Name, 
//				                        Corrective_Action ,Preventive_Action ,
//				                        NPT_Hrs_Loss, Manhours_Loss,Financial_Loss_Amt,Comments,
//                                        " + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Parts_Of_Body',Part_Of_Body_Id_1,'NAME') [Part_Of_Body_Name_1],
//                                        " + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Parts_Of_Body',Part_Of_Body_Id_2,'NAME')  [Part_Of_Body_Name_2],
//                                        " + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Parts_Of_Body',Part_Of_Body_Id_3,'NAME') [Part_Of_Body_Name_3],
//                                        " + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Parts_Of_Body',Part_Of_Body_Id_4,'NAME') [Part_Of_Body_Name_4],
//
//
//				                        Reported_By ,  " + OI.Glo + @"Fnc_Get_Col_Value('" + OI.Glo + @"Mst_Rank',Rptd_By_Rank_Id,'NAME') As Rptd_By_Rank_Name		 
//                        From " + OI.Def + @"Incident_Details
//                    
//                        Where Incident_Id = @Incident_Id
//
//
//                        /*Take the Data Containing Image path*/
//                        Select  Incident_Photo_Path  From " + OI.Def + @"Incident_Photos Where Incident_Photo_Active ='Y' and Incident_Id = @Incident_Id
//                       ";

//            Da = new SqlDataAdapter(strQuery, Conn);
//            Da.SelectCommand.Parameters.Add("@Incident_Id", SqlDbType.Int).Value = Convert.ToInt32(tbIncident_Id_Hidden.Value);

//            Da.Fill(Ds, "Incident_Details");

//            #endregion

//            #region Take the Images in the Syste.Byte array and store it in the DataTable

//            string strGlobalMastersURL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();

//            System.Data.DataTable dtImage = new System.Data.DataTable();
//            dtImage.TableName = "Images";
//            // object of data row 
//            DataRow drImage;
//            // add the column in table to store the image of Byte array type 
//            dtImage.Columns.Add("Emp_Image", System.Type.GetType("System.Byte[]"));

//            if (Ds.Tables["Incident_Details1"].Rows.Count > 0)
//            {
//                for (int intImageCnt = 0; intImageCnt < Ds.Tables["Incident_Details1"].Rows.Count; intImageCnt++)
//                {
//                    drImage = dtImage.NewRow();

//                    string strImpage_File_path = "";

//                    strImpage_File_path = strGlobalMastersURL + Ds.Tables["Incident_Details1"].Rows[intImageCnt]["Incident_Photo_Path"];

//                    try
//                    {

//                        HttpWebRequest lxRequest = (HttpWebRequest)WebRequest.Create(strImpage_File_path);

//                        lxRequest.PreAuthenticate = true;
//                        lxRequest.Credentials = CredentialCache.DefaultCredentials;

//                        // returned values are returned as a stream, then read into a string
//                        String lsResponse = string.Empty;
//                        using (HttpWebResponse lxResponse = (HttpWebResponse)lxRequest.GetResponse())
//                        {
//                            using (BinaryReader reader = new BinaryReader(lxResponse.GetResponseStream()))
//                            {

//                                Byte[] lnByte = reader.ReadBytes((int)lxResponse.ContentLength);
//                                drImage[0] = lnByte;
//                            }
//                        }

//                    }
//                    catch (Exception exep)
//                    {

//                    }
//                    ///Add the Data to the DataTable
//                    dtImage.Rows.Add(drImage);

//                }
//            }


//            Ds.Tables.Add(dtImage);

//            #region These 2 dates are imporatant to decide which header footer to dispay New / Old company
//            string strAuth_Sign_Photo_URL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();
//            string  Effective_Date = tbIncident_Date.Text;
//            string Prj_Cutoff_Date = ConfigurationManager.ConnectionStrings["Prj_Cutoff_Date"].ToString();
//              Int16 intFS_Category_Id = 0;
//            if (Convert.ToInt16(tbRig_Id_Hidden.Value) == 1)///WILDCAT selected
//            {
//                intFS_Category_Id = 5;
//            }
//            else
//            {
//                intFS_Category_Id = 4;
//            }

//            #endregion


//            clsrHeader_Footer_Img clsNew = new clsrHeader_Footer_Img();
//            DataTable dtHeader_Footer = clsNew.Get_Header_Footer_Image_Rig(ref Conn, strAuth_Sign_Photo_URL, "Header_Footer", "Prc_Doc_To_Sign_Mapping", "Get_Header_Footer_Rig_Id", tbRig_Id_Hidden.Value, Effective_Date, Prj_Cutoff_Date, intFS_Category_Id);

//            if (dtHeader_Footer.Rows[0]["stringErr_Msg"].ToString().ToUpper().Contains("ERROR"))
//            {
//                throw new Exception(dtHeader_Footer.Rows[0]["stringErr_Msg"].ToString());

//            }
//            Ds.Tables.Add(dtHeader_Footer);

//            #endregion


//            string PFile = "Acc_Incident_" + Session.SessionID.ToString() + DateTime.Now.ToString("mm") + DateTime.Now.ToString("ss") + ".pdf";
//            string[] Param = new string[1];
//            Param[0] = clsSystem_Generic_Info.Report_Dt_Caption.ToString();
//            clsGen_Crystal_Report.Show_Report(Server.MapPath("~/Reports/Accident_Incident_Report.rpt"), Server.MapPath("~/TempReports"), PFile, Param, ref Ds);


//        }
//        catch (SqlException sqlexep)
//        {
//            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
//            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
//            return;
//        }
//        catch (System.Threading.ThreadAbortException lException)
//        {

//        }
//        catch (Exception exep)
//        {
//            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
//            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
//            return;
//        }
//        finally
//        {
//            if (Conn.State == ConnectionState.Open)
//            {
//                Conn.Close();
//            }
//        }
    //    }
    #endregion

    protected void tbIncident_Date_TextChanged(object sender, EventArgs e)
    {
        if (tbIncident_Id_Hidden.Value == "")
        {
            // as changes on 17/02/2017
            //Set_Max_Incident_No();
            GetCountry_Well();
        }
    }

    protected void btnUpload_Click(object sender, EventArgs e)
    {

        bool blnFile_Uploaded = false;
        string strSession_Id = Session.SessionID;

        if (fupd_ExcelSheet.HasFile)
        {
            string strTemp_File_Path = Server.MapPath("~/TempReports/");

            if (!Directory.Exists(strTemp_File_Path))
            {
                Directory.CreateDirectory(strTemp_File_Path);
            }

            blnFile_Uploaded = UploadFile_Excel(strSession_Id, "~/TempReports/");
           
            if (blnFile_Uploaded == false)
            {
                if ((ErrorString != "") && (ErrorString != null))
                {
                    ClearMe(true);
                    // ErrorString = "<script>alert('" + ErrorString + "');</script>";

                    ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
                    return;
                }
            }
        }
        else
        {
            ErrorString = "<script>alert('Select a file to be uploaded');</script>";
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
        }
    }


    protected bool UploadFile_Excel(string strId, string strPath)
    {
        
        Boolean fileOK = false;
        string strFileName = "";

        String path = HttpContext.Current.Server.MapPath(strPath);

        if (fupd_ExcelSheet.HasFile)
        {
            String fileExtension = System.IO.Path.GetExtension(fupd_ExcelSheet.FileName).ToLower();
            String[] allowedExtensions = { ".xls", ".xlsx" };

            for (int i = 0; i < allowedExtensions.Length; i++)
            {
                if (fileExtension == allowedExtensions[i])
                {
                    fileOK = true;
                }
            }
        }

        if (fileOK)
        {
            try
            {
                strFileName = path + strId + System.IO.Path.GetExtension(fupd_ExcelSheet.FileName).ToLower();
                fupd_ExcelSheet.PostedFile.SaveAs(strFileName);
            }
            catch (Exception ex)
            {
                if (ex.Message.Contains("'"))
                {
                    ErrorString = ex.Message.Replace("'", "");
                }

                ErrorString = "<script>alert('File could not be Uploaded!!![ " + ErrorString + " ]');</script>";
                return false;
            }

            Fill_Dataset(strFileName);

            if (!String.IsNullOrEmpty(ErrorString))
            {
                return false;
            }

        }
        else
        {
            ErrorString = "<script>alert('Invalid File Type!!!.');</script>";
            return false;
        }

        return true;
    }

    protected void Fill_Dataset(string strFileName)
    {

         ClearMe(true);
        DataSet ODs; int intPrmKey_Value;
        try
        {

            ///Fetch all values from the excel sheet into a dataset.
            //OleDbConnection OConn = new OleDbConnection(@"Provider=Microsoft.Ace.OLEDB.12.0;Data Source=" + strFileName + @";Extended Properties=""Excel 12.0;HDR=YES;""");
            
            OleDbConnection OConn = new OleDbConnection();

            if (ConfigurationManager.ConnectionStrings["DebugModeYN"].ToString() == "N")
            {
                OConn = new OleDbConnection(@"Provider=Microsoft.Ace.OLEDB.12.0;Data Source=" + strFileName + @";Extended Properties=""Excel 12.0;HDR=YES;IMEX=1""");
            }
            else
            {
                OConn = new OleDbConnection(@"Provider=Microsoft.Jet.OLEDB.4.0;Data Source=" + strFileName + @";Extended Properties=""Excel 8.0;HDR=YES""");
            }


            string strSql = "SELECT ColumnName,ColumnDataType,UserValues,ActualValues,VersionNo,Upload_FolderName,Output_Parameter FROM [Sheet1$]";

            OleDbDataAdapter ODa = new OleDbDataAdapter(strSql, OConn);

            ODs = new DataSet();

            ODa.Fill(ODs, "Excel_Data");

            /// Delete the uploaded excel file.
            File.Delete(strFileName);
        }
        catch (Exception Ex)
        {
            if (Ex.Message.ToString().Contains("No value given for one or more required parameters"))
            {
                ErrorString = "<script>alert('The file being uploaded is not the correct version..');</script>";
            }
            else
            {
                ErrorString = "<script>alert('" + Ex.Message.ToString() + "')";
            }
            return;
        }

        if (!String.IsNullOrEmpty(ErrorString))
            return;

        SqlConnection Conn = new SqlConnection(strConString);


        if (Conn.State == ConnectionState.Closed)
        {
            Conn.Open();
        }

        SqlTransaction trDML;


        trDML = Conn.BeginTransaction();

        try
        {

            //Get the Excel File Data in DataSet
            Check_Users_AndActual_Values(ref ODs);

            if (ODs.Tables["Excel_Data"].Rows.Count > 0)
            {
                //Because not to consider FIRST ROW which contains SP NAME .
                int TotalCount = ODs.Tables["Excel_Data"].Rows.Count - 1;
                ///Valiation Check that Same values in User Entered and Actual Values Copied field.
                ///Also check the Stored Procedure and the Folder name which required to store file after succesfully upload.                    

                //Check_Users_AndActual_Values(ref ODs);

                string strSp_Name, strUploaded_FolderName = "", strOutput_Parameter = "";

                ///The 3rd Row  In excel (& 2nd Row in DataSet) containts SP Name 
                strSp_Name = ODs.Tables["Excel_Data"].Rows[0]["ColumnName"].ToString();

                ///The 3rd Row In excel (& 2nd Row in DataSet) containts Folder Name where to store Image.     
                ///[1][I(Upload_FolderName)]
                strUploaded_FolderName = ODs.Tables["Excel_Data"].Rows[0]["Upload_FolderName"].ToString();

                ///The 3rd Row In excel (& 2nd Row in DataSet)It will return inserted record's Value.
                ///[1][H(Output_Parameter)]
                strOutput_Parameter = ODs.Tables["Excel_Data"].Rows[0]["Output_Parameter"].ToString();


                ///If stored proc Name Or Uploaded Folder Name is Empty
                if (string.IsNullOrEmpty(strSp_Name) || string.IsNullOrEmpty(strUploaded_FolderName))
                {
                    throw new Exception("Stored Procedure Name / Uploaded Folder Name is not found in Dataset");
                }
                ///Setting destination path for the file.
                SqlCommand CmdDML;


                CmdDML = new SqlCommand(strSp_Name, Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;

                fnc_Add_Params(ref CmdDML, ref Conn, TotalCount, ref ODs);

                ///Output parameter
                if (!string.IsNullOrEmpty(strOutput_Parameter))
                {
                    CmdDML.Parameters.Add(strOutput_Parameter, System.Data.SqlDbType.Int).Direction = ParameterDirection.Output;
                }

                CmdDML.Parameters.Add("Incident_Status", System.Data.SqlDbType.VarChar).Value = "FM";
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Insert";
                CmdDML.ExecuteNonQuery();

                intPrmKey_Value = 0;///This is primary Key generated after INSERT.

                ///If Output_Parameter is mentioned in Excel then Return that Field Value
                if (!string.IsNullOrEmpty(strOutput_Parameter))
                {

                    if (!string.IsNullOrEmpty(CmdDML.Parameters[strOutput_Parameter].Value.ToString()))
                    {
                        intPrmKey_Value = Convert.ToInt32(CmdDML.Parameters[strOutput_Parameter].Value.ToString());
                    }
                    else
                    {
                        throw new Exception("Incident Id is not found");
                    }
                }
                string strFile = strFileName;
                string strFile_Name_Incient_No = "";

                //if (intPrmKey_Value != 0)
                //{
                //    strFile_Name_Incient_No = strFile.Substring(0, strFile.LastIndexOf('.')) + "_" + intPrmKey_Value + strFile.Substring(strFile.LastIndexOf('.'));

                //    string strStatus = Save_Excel_Images(strFile, intPrmKey_Value, ref Conn, ref trDML);
                //    if (!string.IsNullOrEmpty(strStatus))
                //    {
                //        throw new Exception(strStatus);
                //    }

                //}

                tbWkg_Incident_Dtl_Id_Hidden.Value = intPrmKey_Value.ToString();
                Get_Wkg_Incident_Dtl(ref Conn, ref trDML);
                if (!string.IsNullOrEmpty(ErrorString))
                {
                    throw new Exception(ErrorString);
                }
                trDML.Commit();
            }

        }
        catch (SqlException Sqlexep)
        {
            trDML.Rollback();

            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(Sqlexep, ref Conn);
            return;
        }
        catch (Exception Ex)
        {
            trDML.Rollback();
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(Ex, ref Conn);
            return;
        }
        finally
        {

        }

    }

    private void Check_Users_AndActual_Values(ref DataSet ODs)
    {
        if (ODs.Tables["Excel_Data"] != null)
        {
            ODs.Tables["Excel_Data"].Rows.RemoveAt(0);///Header of the Excel file containing description and Version No

            bool bytChk_Values = true;
            bool bytChk_Sp_Folder_Name = true;
            int TotalCount = 0;
            DataView DtView_Filter_RowCount = ODs.Tables["Excel_Data"].DefaultView;
            DtView_Filter_RowCount.RowFilter = "ColumnName = 'FinalRow'";

            System.Data.DataTable Dt_Row_Count = new System.Data.DataTable();
            Dt_Row_Count = DtView_Filter_RowCount.ToTable();

            ///How many records to be inserted .
            TotalCount = Convert.ToInt32(DtView_Filter_RowCount[0]["ColumnDataType"].ToString().Trim());

            //If the data is added in the Dropdown selection of the Excel fiel then version will be increases as  .1 ie 1.4.1 , 1.4.2 like this....
            //
            if (!ODs.Tables["Excel_Data"].Rows[0]["VersionNo"].ToString().Trim().Contains("10.0"))
            {
                ErrorString = "The file being uploaded is not the correct version.";
                throw new Exception(ErrorString);
            }

            if (ODs.Tables["Excel_Data"].Rows.Count > 0)
            {
                for (int intRow = 1; intRow < TotalCount; intRow++)
                {

                    if (ODs.Tables["Excel_Data"].Rows[intRow][0].ToString().Trim() != "" && ODs.Tables["Excel_Data"].Rows[intRow][0].ToString().Trim() != "FinalRow")
                    {


                        //user Entered Value is not Blank and Actual Values are Blank
                        if (ODs.Tables["Excel_Data"].Rows[intRow]["UserValues"].ToString().Trim() != "" && ODs.Tables["Excel_Data"].Rows[intRow]["ActualValues"].ToString().Trim() == "")
                        {
                            ErrorString = "Data in 'User Values' and 'Actual values' are not Same";
                            bytChk_Values = false;
                        }
                    }
                }
                ///The 3rd Row  In excel (& 2nd Row in DataSet) containts SP Name 
                if (ODs.Tables["Excel_Data"].Rows[0]["ColumnName"].ToString().Trim() == "")
                {
                    ErrorString = "Stored Procedure name is missing in excel";
                    bytChk_Sp_Folder_Name = false;
                }
                ///The 3rd Row In excel (& 2nd Row in DataSet) containts Folder Name where to store Image.                            
                if (ODs.Tables["Excel_Data"].Rows[0]["Upload_FolderName"].ToString().Trim() == "")
                {
                    ErrorString = "Folder Name is missing in excel";
                    bytChk_Sp_Folder_Name = false;
                }

            }
            if (bytChk_Values == false || TotalCount == 0 || bytChk_Sp_Folder_Name == false)///If values are not Same and Total Count = 0 then
            {

                throw new Exception(ErrorString);
            }
            else
            {
                ///If Suppose Same Field is Concatened in different Fields then Delete that extra Columns from the DataSet.              
                int intCounter = 0;

                foreach (DataRow row in ODs.Tables["Excel_Data"].Select())
                {
                    if ((row["ColumnName"].ToString() == "ExtraColumn"))
                    {
                        row.Delete();
                    }
                }
                ODs.Tables["Excel_Data"].AcceptChanges();



                foreach (DataRow row in ODs.Tables["Excel_Data"].Select())
                {
                    if (intCounter > TotalCount)
                    {
                        row.Delete();
                    }
                    intCounter = intCounter + 1;
                }
                ODs.Tables["Excel_Data"].AcceptChanges();

            }
        }
    }

    protected void fnc_Add_Params(ref SqlCommand CmdDML, ref SqlConnection Conn, int TotalCnt, ref DataSet ODs)
    {

        ///Started From 1 Because 0th Position containts Stored procedure name
        for (int intRow = 1; intRow <= TotalCnt; intRow++)
        {

            string strVal, strCol_Name, strCol_Data_Type = "";

            ///Column Name
            strCol_Name = ODs.Tables["Excel_Data"].Rows[intRow]["ColumnName"].ToString().Trim();
            ///Column Data Type
            strCol_Data_Type = ODs.Tables["Excel_Data"].Rows[intRow]["ColumnDataType"].ToString().Trim();
            ///Value
            strVal = ODs.Tables["Excel_Data"].Rows[intRow]["ActualValues"].ToString().Trim();

            #region Adding Sql parameters
            switch (strCol_Data_Type.ToUpper())
            {

                case "VARCHAR":
                    {
                        if (!string.IsNullOrEmpty(strVal))
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.VarChar).Value = strVal;
                        }
                        else
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.VarChar).Value = DBNull.Value;
                        }
                        break;
                    }
                case "INT":
                    {
                        if (!string.IsNullOrEmpty(strVal))
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.Int).Value = Convert.ToInt32(strVal);
                        }
                        else
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.Int).Value = DBNull.Value;
                        }
                        break;
                    }
                case "SMALLINT":
                    {
                        if (!string.IsNullOrEmpty(strVal))
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.SmallInt).Value = Convert.ToInt16(strVal);
                        }
                        else
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.SmallInt).Value = DBNull.Value;
                        }
                        break;
                    }
                case "TINYINT":
                    {
                        if (!string.IsNullOrEmpty(strVal))
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.TinyInt).Value = Convert.ToByte(strVal);
                        }
                        else
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.TinyInt).Value = DBNull.Value;
                        }
                        break;
                    }
                case "DATETIME":
                    {
                        if (!string.IsNullOrEmpty(strVal))
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.DateTime).Value = Convert.ToDateTime(DateTime.ParseExact(strVal, "dd-MMM-yy", null));

                        }
                        else
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.DateTime).Value = DBNull.Value;

                        }
                        break;
                    }
                case "DATE":
                    {
                        ///If input date is read in "dd-MMM-yy" format by provider then Lenght is 9 and accordingly IFormatProvider 
                        ///supplied for ParseExact is  "dd-MMM-yy" else "dd/MM/yyyy hh:mm:ss tt".
                        if (!string.IsNullOrEmpty(strVal))
                        {
                            if (strVal.Length == 11)
                                CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.Date).Value = Convert.ToDateTime(DateTime.ParseExact(strVal, "dd-MMM-yyyy", null));
                            else if (strVal.Length == 22)
                                CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.Date).Value = Convert.ToDateTime(DateTime.ParseExact(strVal, "dd/MM/yyyy hh:mm:ss tt", null));
                        }
                        else
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.Date).Value = DBNull.Value;

                        }
                        break;
                    }
                case "DECIMAL":
                    {
                        if (!string.IsNullOrEmpty(strVal))
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.Decimal).Value = Convert.ToDecimal(strVal);
                        }
                        else
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.Decimal).Value = DBNull.Value;
                        }
                        break;
                    }
                case "TIME":
                    {
                        if (!string.IsNullOrEmpty(strVal))
                        {
                            CmdDML.Parameters.Add(new SqlParameter(strCol_Name, SqlDbType.Time)).Value = strVal;
                        }
                        else
                        {
                            CmdDML.Parameters.Add(strCol_Name, System.Data.SqlDbType.Time).Value = DBNull.Value;
                        }
                        break;
                    }

            }
            #endregion

        }
    }


    protected void Bind_Images_File_Upload()
    {

        DataTable tblImage = new DataTable();
        tblImage.Columns.Add("Sr_No");


        int Sr_No = 1;
        for (int i = 0; i < 5; i++)
        {
            DataRow drRow;
            drRow = tblImage.NewRow();
            Sr_No = i + 1;
            drRow["Sr_No"] = Sr_No;
            tblImage.Rows.Add(drRow);
        }

        grdInc_Images.DataSource = tblImage;
        grdInc_Images.DataBind();


    }
    protected void grdUploaded_Images_RowDataBound(object sender, GridViewRowEventArgs e)
    {
        string strSystemURL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();
        //foreach (GridViewRow grdRow in grdUploaded_Images.Rows)
        if (e.Row.RowType == DataControlRowType.DataRow)
        {
            HtmlAnchor lnkDisp_Img = (HtmlAnchor)e.Row.FindControl("lnkDisp_Img");

            HtmlInputHidden tbIncident_Photo_Path = (HtmlInputHidden)e.Row.FindControl("tbIncident_Photo_Path_Hidden");
            HtmlInputHidden tbIncident_Photo_Id = (HtmlInputHidden)e.Row.FindControl("tbIncident_Photo_Id_Hidden");
            ///Append the system Url with the image path To open image in Pop up.
            lnkDisp_Img.Attributes.Add("onclick", "Image_Window('" + strSystemURL + tbIncident_Photo_Path.Value + "');");
        }
    }
    protected void btnDelete_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Delete);
    }

    protected void lbtnDownload_Click(object sender, EventArgs e)
    {
        string strPath = "";
        string strTemplate_Path = "";
        string strTemplate_Physical_path = "";
        string strSystemURL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();

        strPath = "/Excel Forms/Rig Incident Report.xls";
        strTemplate_Path = strSystemURL + strPath;

        strTemplate_Physical_path = HttpContext.Current.Server.MapPath("~" + strPath);

        if (System.IO.File.Exists(strTemplate_Physical_path) == true)
            ClientScript.RegisterStartupScript(this.GetType(), "Open_DownloadTemplate", " Open_DownloadTemplate(" + "'" + strTemplate_Path + "'" + ");", true);

    }
}